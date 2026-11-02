import ExcelJS from 'exceljs';
import {PDFDocument} from 'pdf-lib';
import {generateExport} from '../src/report-routes.js';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
import {today} from '../src/registry.js';
import {loadUser} from '../src/policies.js';
import {hashPassword} from '../src/security.js';
import {config} from '../src/config.js';
import {createApp} from '../src/app.js';
import {reportData} from '../src/reports.js';
import {createTraining,trainingAction,trainingRoster,trainingRecord,personalTrainings,facilitatorTrainingHistory} from '../src/trainings.js';
const course=()=>({title:'Media reporting / മാധ്യമ റിപ്പോർട്ടിംഗ്',trainer:'QA Trainer',session_date:today(),starts_at:'09:00',ends_at:'12:00',mode:'ONLINE',venue:'Private training meeting details',scope:'STATE',reason:'Create synthetic course'});
async function setup(){const db=await database({sqlite:':memory:'});await migrate(db);await seed(db);
 for(const [id,superuser] of [['admin',1],['district',0],['outside',0],['block',0],['viewer',0],['self',0]])await db.run('INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES (?,?,?,?,?)',[id,id,id+'@example.invalid',await hashPassword('Synthetic-password-123'),superuser]);
 for(const [id,role,scope,district,block] of [['district','DISTRICT_ADMIN','DISTRICT','TVM',null],['outside','DISTRICT_ADMIN','DISTRICT','KSD',null],['block','BLOCK_COORDINATOR','BLOCK','TVM','B01011'],['viewer','VIEWER','DISTRICT','TVM',null]])await db.run('INSERT INTO gmf_scopes(id,user_id,role,scope,district_code,block_code) VALUES (?,?,?,?,?,?)',[id,id,role,scope,district,block]);
 for(const [id,p,name,mobile,role] of [['t','G01071','TVM Participant','9876543210','PRIMARY'],['a','G01071','TVM Second','9876543211','ASSISTANT'],['k','G14020','KSD Participant','9876543212','PRIMARY']]){
 await db.run('INSERT INTO gmf_applications(id,number,panchayat_code,payload,full_name,normalized_name,mobile,email,status,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?)',[id,'APP-'+id,p,JSON.stringify({2:{full_name:name,mobile,address:'QA address'},3:{},4:{}}),name,name,mobile,'','APPROVED',0]);
 await db.run('INSERT INTO gmf_facilitators(id,application_id,number,panchayat_code,full_name,role,valid_until,primary_key,approved_by,approved_at) VALUES (?,?,?,?,?,?,?,?,?,?)',[id,id,'MF-'+id,p,name,role,'2099-01-01',role==='PRIMARY'?p:null,'admin',0]);}
 await db.run("INSERT INTO gmf_facilitator_accounts(user_id,facilitator_id) VALUES ('self','t')");return db;}
const rows=(db,id)=>db.all('SELECT * FROM gmf_training_assignments WHERE training_id=? ORDER BY facilitator_id',[id]);
test('assign first, verify individual/bulk attendance, reject stale changes and retain cancelled assignment history',async()=>{const db=await setup();try{
 const id=await createTraining(db,'admin',course());await trainingAction(db,'admin',id,{action:'assign',training_revision:1,facilitator_ids:['t','a'],reason:'Invite local members'});let assignments=await rows(db,id);assert.equal(assignments.length,2);assert.ok(assignments.every(a=>a.attendance==='PENDING'));
 await trainingAction(db,'admin',id,{action:'assign',training_revision:2,facilitator_ids:['t','a'],reason:'Retry assignment'});assert.equal((await rows(db,id)).length,2);
 const first=assignments.find(a=>a.facilitator_id==='t'),second=assignments.find(a=>a.facilitator_id==='a');
 await trainingAction(db,'admin',id,{action:'attendance',training_revision:3,assignment_id:first.id,revision:1,attendance:'LATE',arrival_time:'09:20',reason:'Verified arrival at training desk'});
 await assert.rejects(trainingAction(db,'admin',id,{action:'attendance',training_revision:3,assignment_id:first.id,revision:1,attendance:'ABSENT',reason:'Stale correction'}));
 await assert.rejects(trainingAction(db,'admin',id,{action:'bulk_attendance',training_revision:3,assignment_ids:[first.id,second.id],attendance:'PRESENT',reason:'Must not overwrite marked attendance'}));assert.equal((await rows(db,id)).find(a=>a.id===second.id).attendance,'PENDING');
 await trainingAction(db,'admin',id,{action:'bulk_attendance',training_revision:3,assignment_ids:[second.id],attendance:'PRESENT',reason:'Verified attendance register'});
 const after=await rows(db,id);assert.equal(after.find(a=>a.id===first.id).arrival_time,'09:20');assert.equal(after.find(a=>a.id===second.id).attendance,'PRESENT');
 const f=(await db.all('SELECT number FROM gmf_facilitators WHERE id=?',['t']))[0];assert.equal(f.number,'MF-t');
 await assert.rejects(trainingAction(db,'admin',id,{action:'update',training_revision:3,...course(),session_date:'2020-01-01',status:'SCHEDULED',reason:'Cannot rewrite attended session date'}));
 await trainingAction(db,'admin',id,{action:'assign',training_revision:3,facilitator_ids:['k'],reason:'Additional invitation'});const extra=(await rows(db,id)).find(a=>a.facilitator_id==='k');
 await trainingAction(db,'admin',id,{action:'cancel_assignment',training_revision:4,assignment_id:extra.id,revision:1,reason:'Participant unavailable'});assert.equal((await rows(db,id)).find(a=>a.id===extra.id).state,'CANCELLED');
 await trainingAction(db,'admin',id,{action:'assign',training_revision:4,facilitator_ids:['k'],reason:'Participant available again'});assert.equal((await rows(db,id)).find(a=>a.id===extra.id).state,'ASSIGNED');assert.equal((await rows(db,id)).length,3);
 assert.ok((await db.all("SELECT action FROM gmf_audit WHERE action='training.attendance_recorded'")).length>=2);
 }finally{await db.close();}});

test('training scope and roster never grant permission to another district or facilitator account',async()=>{const db=await setup();try{
 await assert.rejects(createTraining(db,'district',course()));await assert.rejects(createTraining(db,'viewer',course()));await assert.rejects(createTraining(db,'block',{...course(),scope:'DISTRICT',district:'TVM'}));
 const block=await createTraining(db,'block',{...course(),scope:'BLOCK',district:'TVM',block:'B01011'});assert.ok(block);
 const local=await createTraining(db,'district',{...course(),scope:'DISTRICT',district:'TVM'});await assert.rejects(trainingAction(db,'district',local,{action:'assign',training_revision:1,facilitator_ids:['t','k'],reason:'Outside scope'}));assert.equal((await rows(db,local)).length,0);
 const id=await createTraining(db,'admin',course());await trainingAction(db,'admin',id,{action:'assign',training_revision:1,facilitator_ids:['t','k'],reason:'State training'});
 const user=await loadUser(db,'district'),t=await trainingRecord(db,user,id),visible=await trainingRoster(db,user,t);assert.equal(visible.length,1);assert.equal(visible[0].f.id,'t');
 const outsider=(await rows(db,id)).find(a=>a.facilitator_id==='k');await assert.rejects(trainingAction(db,'district',id,{action:'attendance',training_revision:2,assignment_id:outsider.id,revision:1,attendance:'PRESENT',reason:'Not allowed'}));
 await assert.rejects(trainingAction(db,'self',id,{action:'assign',training_revision:2,facilitator_ids:'t',reason:'Self assignment forbidden'}));await assert.rejects(facilitatorTrainingHistory(db,user,'k'));
 const mine=await personalTrainings(db,'self');assert.equal(mine.length,1);assert.equal(mine[0].attendance,'PENDING');assert.equal(mine[0].assignment_state,'ASSIGNED');
 const report=await reportData(db,user,{report:'training_attendance',training:id},true);assert.equal(report.rows.length,1);assert.equal(report.rows[0][2],'MF-t');assert.ok(!JSON.stringify(report.rows).includes('KSD Participant'));
 }finally{await db.close();}});

test('future training attendance is blocked and session completion does not invent attendance',async()=>{const db=await setup();try{
 const future=new Date(today());future.setUTCDate(future.getUTCDate()+1);const id=await createTraining(db,'admin',{...course(),session_date:future.toISOString().slice(0,10)});await trainingAction(db,'admin',id,{action:'assign',training_revision:1,facilitator_ids:'t',reason:'Invite tomorrow'});const a=(await rows(db,id))[0];
 await assert.rejects(trainingAction(db,'admin',id,{action:'attendance',training_revision:2,assignment_id:a.id,revision:1,attendance:'PRESENT',reason:'Premature'}));
 await assert.rejects(trainingAction(db,'admin',id,{action:'update',training_revision:2,...course(),session_date:future.toISOString().slice(0,10),status:'COMPLETED',reason:'Premature completion'}));
 await trainingAction(db,'admin',id,{action:'update',training_revision:2,...course(),status:'COMPLETED',reason:'Actual training was held today'});assert.equal((await rows(db,id))[0].attendance,'PENDING');
 await assert.rejects(trainingAction(db,'admin',id,{action:'assign',training_revision:3,facilitator_ids:'a',reason:'Closed session'}));
 await trainingAction(db,'admin',id,{action:'update',training_revision:3,...course(),status:'CANCELLED',reason:'Cancelled'});await assert.rejects(trainingAction(db,'admin',id,{action:'attendance',training_revision:4,assignment_id:a.id,revision:1,attendance:'PRESENT',reason:'Cancelled course'}));
 }finally{await db.close();}});

test('training staff screens and personal history work over HTTP with CSRF and personal isolation',async()=>{const db=await setup(),cfg=config({});let server;try{
 const id=await createTraining(db,'admin',course());await trainingAction(db,'admin',id,{action:'assign',training_revision:1,facilitator_ids:['t','k'],reason:'Session invitation'});
 const app=await createApp(db,cfg);server=app.listen(0,'127.0.0.1');await new Promise(resolve=>server.once('listening',resolve));cfg.origin=`http://127.0.0.1:${server.address().port}`;
 function client(){let cookie='',csrf='';return async(path,body)=>{const options={redirect:'manual',headers:{cookie}};if(body){options.method='POST';options.headers['content-type']='application/x-www-form-urlencoded';options.body=new URLSearchParams({csrf,...body});}const res=await fetch(cfg.origin+path,options);if(res.headers.get('set-cookie'))cookie=res.headers.get('set-cookie').split(';')[0];const text=await res.text();csrf=text.match(/name="csrf" value="([a-f0-9]+)"/)?.[1]||csrf;return {status:res.status,text,location:res.headers.get('location')};};}
 const staff=client(),self=client();await staff('/accounts/login/');await staff('/accounts/login/',{username:'admin',password:'Synthetic-password-123'});assert.equal((await staff('/trainings/new/')).status,200);
 const page=await staff(`/trainings/${id}/`);assert.equal(page.status,200);assert.ok(page.text.includes('ഹാജർ'));assert.ok(page.text.includes('bulk-attendance'));assert.equal((await staff('/trainings/')).status,200);assert.equal((await staff('/facilitators/t/trainings/')).status,200);
 await self('/accounts/login/');await self('/accounts/login/',{username:'self',password:'Synthetic-password-123'});const mine=await self('/my/trainings/?facilitator_id=k');assert.equal(mine.status,200);assert.ok(mine.text.includes('മാധ്യമ റിപ്പോർട്ടിംഗ്'));assert.ok(!mine.text.includes('KSD Participant'));assert.equal((await self(`/trainings/${id}/`)).location,'/my/');
 const a=(await rows(db,id)).find(a=>a.facilitator_id==='t');assert.equal((await staff(`/trainings/${id}/`,{action:'attendance',training_revision:'2',assignment_id:a.id,revision:'1',attendance:'PRESENT',reason:'Verified attendance'})).status,302);
 assert.ok((await self('/my/trainings/')).text.includes('Present / ഹാജർ'));
 }finally{if(server)await new Promise(resolve=>server.close(resolve));await db.close();}});

test('attendance reports filter the session date, retain late arrival and export Excel PDF CSV',async()=>{const db=await setup(),cfg=config({});try{
 const id=await createTraining(db,'admin',course());await trainingAction(db,'admin',id,{action:'assign',training_revision:1,facilitator_ids:['t','a'],reason:'Attendance report participants'});const assignment=(await rows(db,id)).find(a=>a.facilitator_id==='t');await trainingAction(db,'admin',id,{action:'attendance',training_revision:2,assignment_id:assignment.id,revision:1,attendance:'LATE',arrival_time:'09:15',reason:'Verified at desk'});
 const user=await loadUser(db,'admin'),filters={report:'training_attendance',training:id,start:today(),end:today()};const data=await reportData(db,user,filters,true);assert.equal(data.rows.length,2);assert.ok(data.rows.some(row=>row[8]==='LATE'&&row[9]==='09:15'));assert.ok(data.rows.some(row=>row[8]==='PENDING'));
 for(const format of ['xlsx','pdf','csv']){const output=await generateExport(db,cfg,'admin',filters,{format,reason:'Training attendance export'});assert.ok(output.bytes.length>100);if(format==='xlsx'){const workbook=new ExcelJS.Workbook();await workbook.xlsx.load(output.bytes);assert.equal(workbook.getWorksheet('Report').getRow(4).getCell(9).value,'Attendance');}if(format==='pdf')assert.ok((await PDFDocument.load(output.bytes)).getPageCount()>=1);if(format==='csv')assert.ok(output.bytes.toString('utf8').includes('LATE'));}
 await assert.rejects(generateExport(db,cfg,'viewer',filters,{format:'csv',reason:'Viewer cannot export'}));
 }finally{await db.close();}});
