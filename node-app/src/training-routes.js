import express from 'express';
import {can} from './policies.js';
import {FormError} from './registration-fields.js';
import {today} from './registry.js';
import {placesFor} from './reports.js';
import {budget} from './security.js';
import {attendanceLabels,trainingStatuses,trainingCapability,trainingVisible,trainingRows,trainingRecord,trainingRoster,assignableFacilitators,createTraining,trainingAction,personalTrainings,facilitatorTrainingHistory} from './trainings.js';
export function trainingRoutes(db,cfg){const r=express.Router();
 const queryText=(value,max=150)=>{if(value===undefined)return '';if(typeof value!=='string'||value.length>max)throw new FormError('Invalid training search.');return value.trim();};
 async function createPage(req,res,error=''){
 if(!trainingCapability(res.locals.user,'trainings.manage'))throw new FormError('Training management access denied.',403);
 const places=await placesFor(db,res.locals.user,'trainings.manage'),scopeOptions=[];
 if(can(res.locals.user,'trainings.manage',{district_code:null,block_code:null}))scopeOptions.push('STATE');
 if(places.some(p=>can(res.locals.user,'trainings.manage',{district_code:p.district_code,block_code:null})))scopeOptions.push('DISTRICT');scopeOptions.push('BLOCK');
 res.render('training-create',{places,scopeOptions,error,values:req.method==='POST'?req.body:{session_date:today(),starts_at:'09:00',ends_at:'17:00',mode:'OFFLINE',scope:scopeOptions[0]}});
 }
 r.get('/trainings/',async(req,res)=>{if(!trainingCapability(res.locals.user,'trainings.view'))throw new FormError('Training access denied.',403);const q=queryText(req.query.q).toLowerCase(),rows=[];for(const t of await trainingRows(db)){if(!trainingVisible(res.locals.user,t)||q&&!t.title.toLowerCase().includes(q))continue;const roster=(await trainingRoster(db,res.locals.user,t)).filter(a=>a.state==='ASSIGNED');rows.push({...t,assigned:roster.length,attended:roster.filter(a=>['PRESENT','LATE'].includes(a.attendance)).length,pending:roster.filter(a=>a.attendance==='PENDING').length});}res.render('trainings',{rows,q,mayCreate:trainingCapability(res.locals.user,'trainings.manage')});});
 r.get('/trainings/new/',async(req,res)=>createPage(req,res));
 r.post('/trainings/new/',async(req,res)=>{if(!await budget(db,cfg.secret,'training-create',req.session.userId,30,3600000))throw new FormError('Too many training changes. Try again later.',429);try{const id=await createTraining(db,req.session.userId,req.body);res.redirect(`/trainings/${id}/`);}catch(error){if(!(error instanceof FormError)||error.status!==400)throw error;res.status(400);await createPage(req,res,error.message);}});
 async function detail(req,res,error=''){
 const user=res.locals.user,t=await trainingRecord(db,user,req.params.id),q=queryText(req.query.q),attendance=queryText(req.query.attendance,20);if(attendance&&!Object.hasOwn(attendanceLabels,attendance))throw new FormError('Choose a valid attendance filter.');
 const all=await trainingRoster(db,user,t),roster=all.filter(a=>!attendance||a.attendance===attendance),rawPage=queryText(req.query.page,6)||'1';if(!/^\d{1,6}$/.test(rawPage))throw new FormError('Invalid roster page.');const page=Math.max(1,Number(rawPage)),pages=Math.max(1,Math.ceil(roster.length/50));
 const candidates=(await assignableFacilitators(db,user,t)).filter(f=>!q||[f.full_name,f.number,f.panchayat_name,f.district_code,f.block_code].some(value=>value.toLowerCase().includes(q.toLowerCase())));
 const active=all.filter(a=>a.state==='ASSIGNED'),summary={assigned:active.length,attended:active.filter(a=>['PRESENT','LATE'].includes(a.attendance)).length,late:active.filter(a=>a.attendance==='LATE').length,absent:active.filter(a=>a.attendance==='ABSENT').length,excused:active.filter(a=>a.attendance==='EXCUSED').length,pending:active.filter(a=>a.attendance==='PENDING').length};
 res.render('training-detail',{t,roster:roster.slice((Math.min(page,pages)-1)*50,Math.min(page,pages)*50),candidates:candidates.slice(0,50),candidateCount:candidates.length,q,attendance,attendanceLabels,trainingStatuses,summary,page:Math.min(page,pages),pages,error,mayEdit:can(user,'trainings.manage',t),mayAssign:trainingCapability(user,'trainings.manage'),mayExport:trainingCapability(user,'reports.export'),future:t.session_date>today()});
 }
 r.get('/trainings/:id/',async(req,res)=>detail(req,res));
 r.post('/trainings/:id/',async(req,res)=>{if(!await budget(db,cfg.secret,'training-change',req.session.userId,300,3600000))throw new FormError('Too many training changes. Try again later.',429);try{await trainingAction(db,req.session.userId,req.params.id,req.body);res.redirect(`/trainings/${req.params.id}/`);}catch(error){if(!(error instanceof FormError)||error.status===403||error.status===404)throw error;res.status(error.status);await detail(req,res,error.message);}});
 r.get('/facilitators/:id/trainings/',async(req,res)=>{const history=await facilitatorTrainingHistory(db,res.locals.user,req.params.id);res.render('training-history',{...history,attendanceLabels,personal:false});});
 r.get('/my/trainings/',async(req,res)=>{const rows=await personalTrainings(db,req.session.userId);res.render('training-history',{rows,attendanceLabels,personal:true,f:null});});
 return r;
}
