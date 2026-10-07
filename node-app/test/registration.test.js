import {cancelRegistration} from '../src/registration-cancellation.js';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {PDFDocument,PDFName} from 'pdf-lib';
import {database} from '../src/database.js';
import {config} from '../src/config.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
import {processUpload} from '../src/uploads.js';
import {newDraft,getDraft,saveStep,submit,reviewAction} from '../src/registration-services.js';
import {validateStep} from '../src/registration-fields.js';
import {createApp} from '../src/app.js';
import {hashPassword} from '../src/security.js';
const personal={full_name:'QA Applicant',mobile:'+91 9876543210',address:'Synthetic test address',pin_code:'695001'};
const location={district:'TVM',block:'B01011',panchayat:'G01071'};
async function setup(){const db=await database({sqlite:':memory:'});await migrate(db);await seed(db);return db;}
async function photo(){return processUpload({buffer:await sharp({create:{width:200,height:300,channels:3,background:'#888'}}).png().toBuffer(),originalname:'qa.png',mimetype:'image/png'},true,[50,50,1]);}
async function ready(db){const id=await newDraft(db);await saveStep(db,id,1,1,location);await saveStep(db,id,2,2,personal);await saveStep(db,id,3,3,{years_experience:'0',languages:['Malayalam']});await saveStep(db,id,4,4,{});await saveStep(db,id,5,5,{}, {photo:await photo()});return id;}
const consent={accuracy:'on',processing:'on',consent_version:'1.0'};
test('field validation rejects forged hierarchy, contacts, dates, choices and URL protocols',async()=>{const db=await setup();try{
 await assert.rejects(validateStep(db,1,{...location,district:'KSD'}));
 for(const bad of [{mobile:'123'},{pin_code:'000000'},{date_of_birth:'2020-02-31'},{emergency_name:'Incomplete'},{email:'bad'}, {full_name:['bad']}])await assert.rejects(validateStep(db,2,{...personal,...bad}));
 await assert.rejects(validateStep(db,3,{years_experience:'81',languages:['Malayalam']}));await assert.rejects(validateStep(db,3,{years_experience:'0',languages:['Other']}));await assert.rejects(validateStep(db,4,{facebook:'javascript:alert(1)'}));
 const valid=await validateStep(db,2,personal);assert.equal(valid.mobile,'9876543210');assert.equal(valid.whatsapp,valid.mobile);
 }finally{await db.close();}});
test('uploads normalize images, strip metadata, and reject malformed/active PDFs',async()=>{
 const result=await photo();assert.equal(result.mime,'image/jpeg');const meta=await sharp(Buffer.from(result.body,'base64')).metadata();assert.equal(meta.exif,undefined);assert.equal(meta.width/meta.height,.75);
 await assert.rejects(processUpload({buffer:Buffer.from('not an image'),originalname:'x.jpg',mimetype:'image/jpeg'},true,[50,50,1]));
 const document=await PDFDocument.create();document.addPage();const bytes=await document.save();const pdf=await processUpload({buffer:Buffer.from(bytes),originalname:'safe.pdf',mimetype:'application/pdf'},false);assert.equal(pdf.mime,'application/pdf');
 document.catalog.set(PDFName.of('OpenAction'),document.context.obj({S:'JavaScript',JS:'alert(1)'}));await assert.rejects(processUpload({buffer:Buffer.from(await document.save()),originalname:'unsafe.pdf',mimetype:'application/pdf'},false));
});
test('draft revisions, consent, duplicate approval and primary appointment race are enforced',async()=>{
 const db=await setup();try{
 const id=await newDraft(db);await assert.rejects(saveStep(db,id,2,1,personal));await saveStep(db,id,1,1,location);await assert.rejects(saveStep(db,id,1,1,location));await assert.rejects(submit(db,id,2,consent));
 await db.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,1)',['admin','testadmin','admin@example.invalid','unused']);
 const first=await ready(db),second=await ready(db);await assert.rejects(submit(db,first,6,{...consent,processing:''}));await submit(db,first,6,consent);await submit(db,second,6,consent);assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_applications'))[0].n,2);await submit(db,first,6,consent);assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_applications'))[0].n,2);
 await assert.rejects(saveStep(db,first,2,7,personal));
 for(const app of [first,second])await reviewAction(db,'admin',app,{action:'start_review',revision:'1'});
 await assert.rejects(reviewAction(db,'admin',first,{action:'approve',revision:'2',verified:'on',role:'PRIMARY'}));
 const decision={action:'approve',revision:'2',verified:'on',acknowledge:'on',reason:'Synthetic duplicates verified.',role:'PRIMARY'};
 const results=await Promise.allSettled([reviewAction(db,'admin',first,decision),reviewAction(db,'admin',second,decision)]);assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_facilitators'))[0].n,1);
 const pending=(await db.all("SELECT id FROM gmf_applications WHERE status='UNDER_REVIEW'"))[0];await assert.rejects(reviewAction(db,'admin',pending.id,{action:'reject',revision:'2'}));await reviewAction(db,'admin',pending.id,{action:'reject',revision:'2',reason:'Synthetic rejection.'});
 }finally{await db.close();}
});
test('public HTTP wizard submits privately; reviewer may review but cannot approve or read another district',async()=>{
 const db=await setup();let server;try{
 const cfg=config({}),app=await createApp(db,cfg);server=app.listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));const base=`http://127.0.0.1:${server.address().port}`;cfg.origin=base;
 function client(){let cookie='',csrf='';return async(url,body)=>{const options={redirect:'manual',headers:{cookie}};if(body){options.method='POST';if(body instanceof FormData){body.set('csrf',csrf);options.body=body;}else{options.headers['content-type']='application/x-www-form-urlencoded';options.body=new URLSearchParams({csrf,...body});}}const response=await fetch(base+url,options);if(response.headers.get('set-cookie'))cookie=response.headers.get('set-cookie').split(';')[0];const text=await response.text();csrf=text.match(/name="csrf" value="([a-f0-9]+)"/)?.[1]||csrf;return {status:response.status,text,location:response.headers.get('location')};};}
 const applicant=client(),stranger=client(),staff=client();assert.equal((await applicant('/register/')).status,200);assert.equal((await applicant('/register/',{})).status,302);
 for(const [step,body] of [[1,location],[2,personal],[3,{years_experience:'0',languages:'Malayalam'}],[4,{}]]){assert.equal((await applicant(`/register/${step}/`)).status,200);assert.equal((await applicant(`/register/${step}/`,{revision:String(step),...body})).status,302);}
 assert.equal((await applicant('/register/5/')).status,200);const form=new FormData();form.set('revision','5');form.set('photo',new Blob([Buffer.from((await photo()).body,'base64')],{type:'image/jpeg'}),'qa.jpg');assert.equal((await applicant('/register/5/',form)).status,302);
 assert.equal((await stranger('/register/files/photo')).status,410);assert.equal((await applicant('/register/6/')).status,200);assert.equal((await applicant('/register/6/',{revision:'6',...consent})).status,302);assert.match((await applicant('/register/complete/')).text,/GS-APP-/);
 const row=(await db.all('SELECT id FROM gmf_applications'))[0];await db.run('INSERT INTO gmf_users(id,username,email,password_hash) VALUES (?,?,?,?)',['reviewer','reviewer','reviewer@example.invalid',await hashPassword('test-password-123')]);await db.run("INSERT INTO gmf_scopes(id,user_id,role,scope,district_code) VALUES ('scope','reviewer','REVIEWER','DISTRICT','TVM')");
 await staff('/accounts/login/');assert.equal((await staff('/accounts/login/',{username:'reviewer',password:'test-password-123'})).status,302);assert.equal((await staff('/applications/')).status,200);assert.equal((await staff(`/applications/${row.id}/`)).status,200);assert.equal((await staff(`/applications/${row.id}/`,{action:'start_review',revision:'1'})).status,302);assert.equal((await staff(`/applications/${row.id}/`,{action:'approve',revision:'2',role:'PRIMARY',verified:'on'})).status,404);
 await db.run("UPDATE gmf_scopes SET district_code='KSD' WHERE id='scope'");assert.equal((await staff(`/applications/${row.id}/`)).status,404);assert.equal((await staff(`/applications/${row.id}/files/photo`)).status,404);
 }finally{if(server)await new Promise(r=>server.close(r));await db.close();}
});


test('discard removes only an unfinished draft; withdrawal retains records and blocks approval',async()=>{
 const db=await setup();try{
 const id=await ready(db),other=await ready(db);
 await assert.rejects(cancelRegistration(db,id,'discard',{revision:6}));
 await assert.rejects(cancelRegistration(db,id,'discard',{revision:5,confirmed:'on'}));
 await cancelRegistration(db,id,'discard',{revision:6,confirmed:'on'});
 assert.equal((await db.all('SELECT id FROM gmf_drafts WHERE id=?',[id])).length,0);
 assert.equal((await db.all('SELECT slot FROM gmf_uploads WHERE owner_id=?',[id])).length,0);
 assert.equal((await getDraft(db,other)).revision,6);
 await submit(db,other,6,{accuracy:'on',processing:'on',consent_version:'1.0'});
 await assert.rejects(cancelRegistration(db,other,'discard',{revision:7,confirmed:'on'}));
 await assert.rejects(cancelRegistration(db,'not-owned','withdraw',{revision:1,confirmed:'on',reason:'Wrong session'}));
 const before=(await db.all('SELECT revision FROM gmf_applications WHERE id=?',[other]))[0];
 await db.run('INSERT INTO gmf_corrections(id,application_id,digest,fields,message,expires_at) VALUES (?,?,?,?,?,?)',['cancel-ticket',other,'a'.repeat(64),'[]','Synthetic',Date.now()+100000]);
 await cancelRegistration(db,other,'withdraw',{revision:before.revision,confirmed:'on',reason:'Applicant withdrew'});
 assert.equal((await db.all('SELECT status FROM gmf_applications WHERE id=?',[other]))[0].status,'WITHDRAWN');
 assert.equal((await db.all('SELECT used FROM gmf_corrections WHERE application_id=?',[other]))[0].used,1);
 assert.equal((await db.all('SELECT slot FROM gmf_uploads WHERE owner_id=?',[other])).length,1);
 assert.equal((await db.all("SELECT actor_id FROM gmf_review_events WHERE action='withdraw'"))[0].actor_id,'APPLICANT');
 await assert.rejects(cancelRegistration(db,other,'withdraw',{revision:before.revision+1,confirmed:'on',reason:'Repeat'}));
 await db.run("UPDATE gmf_applications SET status='APPROVED' WHERE id=?",[other]);
 await assert.rejects(cancelRegistration(db,other,'withdraw',{revision:before.revision+1,confirmed:'on',reason:'Approved'}));
 }finally{await db.close();}
});
