import express from 'express';
import {settings} from './settings.js';
import {correctionTicket,correctionChoices} from './corrections.js';
import multer from 'multer';
import {budget,validCsrf} from './security.js';
import {can} from './policies.js';
import {FormError,fields,titles,catalog,slots} from './registration-fields.js';
import {processUpload,maxFileBytes} from './uploads.js';
import {newDraft,getDraft,saveStep,submit,applicationSelect,getApplication,duplicates,reviewAction} from './registration-services.js';
export function uploadMiddleware(db,cfg){
 const parse=multer({storage:multer.memoryStorage(),limits:{fileSize:maxFileBytes,files:5,fields:80,fieldSize:4096,parts:85}}).fields(slots.map(name=>({name,maxCount:1})));let inFlight=0;
 return async(req,res,next)=>{
 if(req.method!=='POST'||!req.is('multipart/form-data'))return next();
 const correction=['/corrections/edit/','/corrections/edit'].includes(req.path);
 if(!correction&&!['/register/5/','/register/5'].includes(req.path))return res.sendStatus(415);
 if(req.headers.origin&&req.headers.origin!==cfg.origin)return res.sendStatus(403);
 if(inFlight>=3||!await budget(db,cfg.secret,'uploads',req.ip,20))return res.status(429).send('Please wait before uploading again.');
 if(correction)await correctionTicket(db,req.session.correctionHash);else {const draft=await getDraft(db,req.session.draftId);if(draft.submitted||draft.completed<4)return res.sendStatus(409);}
 inFlight++;let done=false;const release=()=>{if(!done){done=true;inFlight--;}};res.once('finish',release);res.once('close',release);
 parse(req,res,error=>{if(error){release();return next(new FormError('Upload up to five files, each no larger than 5 MB.',413));}next();});
 };
}
export function publicRegistration(db,cfg){
 const r=express.Router();
 r.get('/register/',async(req,res)=>res.render('register-start',{hasDraft:!!req.session.draftId,registrationOpen:(await settings(db,'system')).data.registration_open}));
 r.post('/register/',async(req,res)=>{
 if(!await budget(db,cfg.secret,'new-draft',req.ip,10))throw new FormError('Too many new drafts. Please try again later.',429);
 if(req.session.draftId){try{const d=await getDraft(db,req.session.draftId);if(!d.submitted)return res.redirect('/register/'+Math.min(d.completed+1,6)+'/');}catch(e){if(!(e instanceof FormError))throw e;}}
 req.session.draftId=await newDraft(db);res.redirect('/register/1/');
 });
 async function renderStep(req,res,step,error='',values){
 const d=await getDraft(db,req.session.draftId);if(d.submitted)return res.redirect('/register/complete/');if(step>d.completed+1)throw new FormError('Complete the previous steps first.');
 const locations=step===1?await db.all(`SELECT p.code,p.name,b.code AS block_code,b.name AS block_name,d.code AS district_code,d.name AS district_name FROM gmf_panchayats p JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code JOIN gmf_states s ON s.code=d.state_code WHERE p.active=1 AND b.active=1 AND d.active=1 AND s.active=1 ORDER BY d.name,b.name,p.name`):[];
 const uploads=await db.all('SELECT slot FROM gmf_uploads WHERE owner_id=?',[d.id]);const policy=(await db.all('SELECT consent_version FROM gmf_registration_policy WHERE id=1'))[0];
 const selected=d.data[1]||{};const reviewLocation=(await db.all('SELECT d.name AS district,b.name AS block,p.name AS panchayat FROM gmf_panchayats p JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code WHERE p.code=? AND b.code=? AND d.code=?',[selected.panchayat||'',selected.block||'',selected.district||'']))[0]||{};
 res.render('register-step',{step,reviewLocation,draft:d,values:values||d.data[step]||{},fields:fields[step]||[],titles,catalog,locations,uploads:uploads.map(u=>u.slot),error,requiredDocuments:(await settings(db,'system')).data.required_documents,version:policy.consent_version});
 }
 r.get('/register/complete/',async(req,res)=>{
 const a=(await db.all('SELECT number FROM gmf_applications WHERE id=?',[req.session.draftId||'']))[0];if(!a)throw new FormError('No submitted application in this session.',404);res.render('register-complete',{number:a.number});
 });
 r.get('/register/files/:slot',async(req,res)=>{
 const d=await getDraft(db,req.session.draftId);const u=(await db.all('SELECT mime,body FROM gmf_uploads WHERE owner_id=? AND slot=?',[d.id,req.params.slot]))[0];if(!u)throw new FormError('File unavailable.',404);sendFile(res,u,req.params.slot);
 });
 r.get('/register/:step/',async(req,res)=>{const step=Number(req.params.step);if(!Number.isInteger(step)||step<1||step>6)throw new FormError('Page unavailable.',404);await renderStep(req,res,step);});
 r.post('/register/:step/',async(req,res)=>{
 const step=Number(req.params.step);if(!Number.isInteger(step)||step<1||step>6)throw new FormError('Page unavailable.',404);
 if(!await budget(db,cfg.secret,'registration-save',req.ip,120))throw new FormError('Too many changes. Please try again later.',429);
 try{
 if(step===6){await submit(db,req.session.draftId,req.body.revision,req.body);return res.redirect('/register/complete/');}
 const processed={};if(step===5){const crop=['crop_x','crop_y','crop_zoom'].map((key,i)=>Number(req.body[key]??[50,50,1][i]));for(const slot of slots)if(req.files?.[slot]?.[0])processed[slot]=await processUpload(req.files[slot][0],slot==='photo',crop);}
 await saveStep(db,req.session.draftId,step,req.body.revision,req.body,processed);res.redirect(`/register/${step+1}/`);
 }catch(e){if(!(e instanceof FormError))throw e;res.status(e.status);await renderStep(req,res,step,e.message,req.body);}
 });
 return r;
}
function sendFile(res,u,slot){res.set({'Content-Type':u.mime,'Content-Disposition':`${slot==='photo'?'inline':'attachment'}; filename="${slot==='photo'?'photo':'document'}.${u.mime==='application/pdf'?'pdf':'jpg'}"`,'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'});res.send(Buffer.from(u.body,'base64'));}
export function staffApplications(db){
 const r=express.Router();
 r.get('/applications/',async(req,res)=>{
 const rows=(await db.all(applicationSelect+' ORDER BY a.submitted_at DESC')).filter(a=>can(res.locals.user,'applications.view',a));
 if(!res.locals.user.superuser&&!res.locals.user.scopes?.some(s=>can({...res.locals.user,scopes:[s]},'applications.view',{district_code:s.district_code,block_code:s.block_code})))throw new FormError('Access denied.',403);
 res.render('applications',{rows});
 });
 r.get('/applications/:id/',async(req,res)=>{
 const a=await getApplication(db,req.params.id,res.locals.user),warnings=await duplicates(db,a);
 const events=await db.all('SELECT action,from_status,to_status,reason,created_at FROM gmf_review_events WHERE application_id=? ORDER BY created_at',[a.id]);
 const uploads=await db.all('SELECT slot FROM gmf_uploads WHERE owner_id=?',[a.id]);const facilitator=(await db.all('SELECT number,role,valid_until FROM gmf_facilitators WHERE application_id=?',[a.id]))[0];
 res.render('application-detail',{correctionChoices,application:a,fields,catalog,events,uploads,facilitator,warnings:warnings.length,canReview:can(res.locals.user,'applications.review',a),canApprove:can(res.locals.user,'applications.approve',a),canContacts:can(res.locals.user,'contacts.view',a)});
 });
 r.post('/applications/:id/',async(req,res)=>{await reviewAction(db,res.locals.user.id,req.params.id,req.body);res.redirect(`/applications/${req.params.id}/`);});
 r.get('/applications/:id/files/:slot',async(req,res)=>{
 const a=await getApplication(db,req.params.id,res.locals.user);if(!can(res.locals.user,'contacts.view',a))throw new FormError('File unavailable.',404);
 const u=(await db.all('SELECT mime,body FROM gmf_uploads WHERE owner_id=? AND slot=?',[a.id,req.params.slot]))[0];if(!u)throw new FormError('File unavailable.',404);sendFile(res,u,req.params.slot);
 });
 return r;
}
