import {createApp} from '../src/app.js';
import {hashPassword} from '../src/security.js';
import {decideApprovedCorrection} from '../src/approved-corrections.js';
import {config} from '../src/config.js';
import {cardState} from '../src/cards.js';
import {loadUser} from '../src/policies.js';
import {facilitator} from '../src/registry.js';
import sharp from 'sharp';
import {processUpload} from '../src/uploads.js';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
import {newDraft,saveStep,submit,reviewAction} from '../src/registration-services.js';
import {requestCorrection,correctionTicket,applyCorrection,digest} from '../src/corrections.js';
import {registryAction,expireFacilitators,today} from '../src/registry.js';
async function setup(){const db=await database({sqlite:':memory:'});await migrate(db);await seed(db);await db.run("INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES ('admin','admin','admin@example.invalid','unused',1)");return db;}
async function application(db){const id=await newDraft(db);await saveStep(db,id,1,1,{district:'TVM',block:'B01011',panchayat:'G01071'});await saveStep(db,id,2,2,{full_name:'Synthetic Applicant',mobile:String(9876543210+(await db.all('SELECT COUNT(*) AS n FROM gmf_applications'))[0].n),address:'Test address',pin_code:'695001'});await saveStep(db,id,3,3,{years_experience:'0',languages:'Malayalam'});await saveStep(db,id,4,4,{});await saveStep(db,id,5,5,{}, {photo:await processUpload({buffer:await sharp({create:{width:200,height:300,channels:3,background:'#888'}}).jpeg().toBuffer(),originalname:'fixture.jpg',mimetype:'image/jpeg'},true,[50,50,1])});await submit(db,id,6,{accuracy:'on',processing:'on',consent_version:'1.0'});await reviewAction(db,'admin',id,{action:'start_review',revision:1});return id;}
const decision={action:'approve',revision:2,role:'PRIMARY',verified:'on',acknowledge:'on',reason:'Synthetic records verified.'};
test('correction tickets restrict fields, require consent, expire, rotate, cancel and prevent replay',async()=>{const db=await setup();try{
 const id=await application(db);const token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:2,reason:'Correct your name.',allowed_fields:['full_name']});const hash=digest(token);assert.equal((await correctionTicket(db,hash)).revision,3);
 await assert.rejects(applyCorrection(db,hash,{revision:3,full_name:'Corrected Name'}));
 await applyCorrection(db,hash,{revision:3,full_name:'Corrected Name',mobile:'8888888888',accuracy:'on',processing:'on',consent_version:'1.0'});
 const a=(await db.all('SELECT * FROM gmf_applications WHERE id=?',[id]))[0];assert.equal(a.status,'SUBMITTED');assert.equal(a.full_name,'Corrected Name');assert.equal(a.mobile,'9876543210');await assert.rejects(correctionTicket(db,hash));
 await reviewAction(db,'admin',id,{action:'start_review',revision:4});const old=await requestCorrection(db,'admin',id,{action:'request_correction',revision:5,reason:'Correct address.',allowed_fields:'address'});const fresh=await requestCorrection(db,'admin',id,{action:'renew_correction',revision:6,reason:'Renewed instructions.'});await assert.rejects(correctionTicket(db,digest(old)));assert(await correctionTicket(db,digest(fresh)));await db.run('UPDATE gmf_corrections SET expires_at=0 WHERE digest=?',[digest(fresh)]);await assert.rejects(correctionTicket(db,digest(fresh)));await requestCorrection(db,'admin',id,{action:'cancel_correction',revision:7,reason:'Cancelled request.'});assert.equal((await db.all('SELECT status FROM gmf_applications WHERE id=?',[id]))[0].status,'UNDER_REVIEW');
 }finally{await db.close();}});
test('registry protects revision, primary occupancy, destination scope, expiry and terminal states',async()=>{const db=await setup();try{
 const app=await application(db);await reviewAction(db,'admin',app,decision);const f=(await db.all('SELECT * FROM gmf_facilitators'))[0];
 await registryAction(db,'admin',f.id,{action:'suspend',revision:1,reason:'Test suspension.'});assert.equal((await db.all('SELECT primary_key FROM gmf_facilitators WHERE id=?',[f.id]))[0].primary_key,null);await assert.rejects(registryAction(db,'admin',f.id,{action:'reactivate',revision:1,reason:'Stale request.'}));
 const candidate=await application(db);await reviewAction(db,'admin',candidate,decision);await assert.rejects(registryAction(db,'admin',f.id,{action:'reactivate',revision:2,reason:'Conflict.'}));
 const other=(await db.all('SELECT id FROM gmf_facilitators WHERE application_id=?',[candidate]))[0];await registryAction(db,'admin',other.id,{action:'revoke',revision:1,reason:'Test revocation.'});await assert.rejects(registryAction(db,'admin',other.id,{action:'renew',revision:2,reason:'Terminal record.'}));
 await registryAction(db,'admin',f.id,{action:'reactivate',revision:2,reason:'Conflict resolved.'});
 await db.run("INSERT INTO gmf_users(id,username,email,password_hash) VALUES ('district','district','district@example.invalid','unused')");await db.run("INSERT INTO gmf_scopes(id,user_id,role,scope,district_code) VALUES ('scope','district','DISTRICT_ADMIN','DISTRICT','TVM')");
 await assert.rejects(registryAction(db,'district',f.id,{action:'transfer',revision:3,panchayat:'G14020',reason:'Out of scope.'}));await registryAction(db,'district',f.id,{action:'transfer',revision:3,panchayat:'G01069',reason:'Transfer within district.'});
 await registryAction(db,'admin',f.id,{action:'role',revision:4,role:'ASSISTANT',reason:'Role change.'});await registryAction(db,'admin',f.id,{action:'resign',revision:5,reason:'Resignation.'});await registryAction(db,'admin',f.id,{action:'reactivate',revision:6,reason:'New appointment.'});
 await db.run("UPDATE gmf_facilitators SET valid_until='2020-01-01' WHERE id=?",[f.id]);assert.equal(await expireFacilitators(db),1);assert.equal(await expireFacilitators(db),0);const date=new Date(today());date.setUTCDate(date.getUTCDate()+365);await registryAction(db,'admin',f.id,{action:'renew',revision:8,valid_until:date.toISOString().slice(0,10),reason:'Renew expired identity.'});assert.equal((await db.all('SELECT status FROM gmf_facilitators WHERE id=?',[f.id]))[0].status,'ACTIVE');
 }finally{await db.close();}});
test('replacement is atomic when approval fails and freezes predecessor after success',async()=>{const db=await setup();try{
 const original=await application(db);await reviewAction(db,'admin',original,decision);const f=(await db.all('SELECT id FROM gmf_facilitators'))[0];const replacement=await application(db);const input={action:'replace',revision:1,replacement_id:replacement,application_revision:2,reason:'Replace test record.',verified:'on',acknowledge:'on'};
 await assert.rejects(registryAction(db,'admin',f.id,{...input,verified:''}));assert.equal((await db.all('SELECT status FROM gmf_facilitators WHERE id=?',[f.id]))[0].status,'ACTIVE');assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_facilitators'))[0].n,1);
 await registryAction(db,'admin',f.id,input);assert.equal((await db.all('SELECT status FROM gmf_facilitators WHERE id=?',[f.id]))[0].status,'REPLACED');assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_facilitators WHERE primary_key IS NOT NULL'))[0].n,1);await assert.rejects(registryAction(db,'admin',f.id,{action:'reactivate',revision:2,reason:'Cannot restore predecessor.'}));
 }finally{await db.close();}});

test('approved corrections stage changes and reapprove without changing any reference or card number',async()=>{const db=await setup(),cfg=config({});try{
 const id=await application(db);await reviewAction(db,'admin',id,decision,cfg);const before=(await db.all('SELECT * FROM gmf_applications WHERE id=?',[id]))[0],f=(await db.all('SELECT * FROM gmf_facilitators'))[0],card=(await db.all('SELECT * FROM gmf_cards'))[0];
 const token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:3,reason:'Correct the spelling of your name.',allowed_fields:['full_name','photo']});
 const image=await processUpload({buffer:await sharp({create:{width:220,height:330,channels:3,background:'#335577'}}).jpeg().toBuffer(),originalname:'replacement.jpg',mimetype:'image/jpeg'},true,[50,50,1]);
 const ticket=await correctionTicket(db,digest(token));assert.equal(ticket.approvedCorrection,true);
 const oldPhoto=(await db.all("SELECT sha256 FROM gmf_uploads WHERE owner_id=? AND slot='photo'",[id]))[0].sha256;
 await applyCorrection(db,digest(token),{revision:4,full_name:'Corrected Approved Name',accuracy:'on',processing:'on',consent_version:'1.0'},{photo:image});
 assert.equal((await db.all('SELECT full_name FROM gmf_applications WHERE id=?',[id]))[0].full_name,before.full_name);assert.equal((await db.all("SELECT sha256 FROM gmf_uploads WHERE owner_id=? AND slot='photo'",[id]))[0].sha256,oldPhoto);
 assert.equal(await cardState(db,card,await facilitator(db,f.id,await loadUser(db,'admin')),cfg),'CURRENT');await assert.rejects(correctionTicket(db,digest(token)));
 const change=(await db.all("SELECT * FROM gmf_approved_corrections WHERE application_id=? AND state='SUBMITTED'",[id]))[0];
 await decideApprovedCorrection(db,cfg,'admin',id,{correction_id:change.id,revision:4,action:'approve',verified:'on',reason:'Corrected spelling and portrait verified.'});
 const after=(await db.all('SELECT * FROM gmf_applications WHERE id=?',[id]))[0],afterF=(await db.all('SELECT * FROM gmf_facilitators'))[0],afterCard=(await db.all('SELECT * FROM gmf_cards'))[0];
 assert.equal(change.original_payload,before.payload);assert.equal(after.number,before.number);assert.equal(after.status,'APPROVED');assert.equal(afterF.id,f.id);assert.equal(afterF.number,f.number);assert.equal(afterF.full_name,'Corrected Approved Name');assert.equal(afterCard.id,card.id);assert.equal(afterCard.number,card.number);assert.equal(afterCard.token,card.token);assert.notEqual(afterCard.pdf_hash,card.pdf_hash);assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_card_revisions'))[0].n,1);
 assert.equal(await cardState(db,afterCard,await facilitator(db,f.id,await loadUser(db,'admin')),cfg),'CURRENT');
 await assert.rejects(decideApprovedCorrection(db,cfg,'admin',id,{correction_id:change.id,revision:4,action:'approve',verified:'on',reason:'Replay'}));
 }finally{await db.close();}});

test('approved correction rejection, cancellation, permissions and stale data preserve approved records',async()=>{const db=await setup(),cfg=config({});try{
 const id=await application(db);await reviewAction(db,'admin',id,decision,cfg);const initial=(await db.all('SELECT * FROM gmf_applications WHERE id=?',[id]))[0];
 await db.run("INSERT INTO gmf_users(id,username,email,password_hash) VALUES ('viewer','viewer','viewer@example.invalid','unused')");
 await assert.rejects(requestCorrection(db,'viewer',id,{action:'request_correction',revision:3,reason:'Unauthorized',allowed_fields:'full_name'}));
 let token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:3,reason:'Fix name',allowed_fields:'full_name'});
 await applyCorrection(db,digest(token),{revision:4,full_name:'Rejected correction',accuracy:'on',processing:'on',consent_version:'1.0'});
 let change=(await db.all("SELECT * FROM gmf_approved_corrections WHERE state='SUBMITTED'"))[0];
 await assert.rejects(decideApprovedCorrection(db,cfg,'viewer',id,{correction_id:change.id,revision:4,action:'approve',verified:'on',reason:'Unauthorized'}));
 await decideApprovedCorrection(db,cfg,'admin',id,{correction_id:change.id,revision:4,action:'reject',reason:'Incorrect information'});
 assert.equal((await db.all('SELECT payload FROM gmf_applications WHERE id=?',[id]))[0].payload,initial.payload);
 token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:5,reason:'Try again',allowed_fields:'full_name'});
 await requestCorrection(db,'admin',id,{action:'cancel_correction',revision:6,reason:'Applicant cancelled'});await assert.rejects(correctionTicket(db,digest(token)));
 token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:7,reason:'Fix spelling',allowed_fields:'full_name'});await applyCorrection(db,digest(token),{revision:8,full_name:'Stale change',accuracy:'on',processing:'on',consent_version:'1.0'});
 change=(await db.all("SELECT * FROM gmf_approved_corrections WHERE state='SUBMITTED'"))[0];await db.run('UPDATE gmf_applications SET revision=revision+1 WHERE id=?',[id]);
 await assert.rejects(decideApprovedCorrection(db,cfg,'admin',id,{correction_id:change.id,revision:9,action:'approve',verified:'on',reason:'Stale correction'}));
 assert.equal((await db.all('SELECT full_name FROM gmf_applications WHERE id=?',[id]))[0].full_name,initial.full_name);
 }finally{await db.close();}});

test('approved correction staff page exposes request and proposed-change review controls',async()=>{const db=await setup(),cfg=config({});let server;try{
 const id=await application(db);await reviewAction(db,'admin',id,decision,cfg);await db.run("UPDATE gmf_users SET password_hash=? WHERE id='admin'",[await hashPassword('Synthetic-test-password-123')]);
 const app=await createApp(db,cfg);server=app.listen(0,'127.0.0.1');await new Promise(resolve=>server.once('listening',resolve));cfg.origin=`http://127.0.0.1:${server.address().port}`;
 let response=await fetch(cfg.origin+'/accounts/login/'),cookie=response.headers.get('set-cookie').split(';')[0],html=await response.text(),csrf=html.match(/name="csrf" value="([a-f0-9]+)"/)[1];
 response=await fetch(cfg.origin+'/accounts/login/',{method:'POST',redirect:'manual',headers:{cookie,'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf,username:'admin',password:'Synthetic-test-password-123'})});cookie=response.headers.get('set-cookie').split(';')[0];
 response=await fetch(cfg.origin+`/applications/${id}/`,{headers:{cookie}});assert.equal(response.status,200);html=await response.text();assert.ok(html.includes('Create correction link'));
 const token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:3,reason:'Correct name',allowed_fields:'full_name'});
 await applyCorrection(db,digest(token),{revision:4,full_name:'Proposed staff review',accuracy:'on',processing:'on',consent_version:'1.0'});
 response=await fetch(cfg.origin+`/applications/${id}/`,{headers:{cookie}});assert.equal(response.status,200);html=await response.text();assert.ok(html.includes('Proposed staff review'));assert.ok(html.includes('Approve corrections — keep numbers'));assert.ok(html.includes('Reject corrections — keep approved details'));assert.ok(!html.includes('Renew correction link'));
 }finally{if(server)await new Promise(resolve=>server.close(resolve));await db.close();}});

test('card rendering failure rolls corrected data back and keeps the staged request reviewable',async()=>{const db=await setup(),cfg=config({});try{
 const id=await application(db);await reviewAction(db,'admin',id,decision,cfg);const before=(await db.all('SELECT payload FROM gmf_applications WHERE id=?',[id]))[0].payload;
 const token=await requestCorrection(db,'admin',id,{action:'request_correction',revision:3,reason:'Correct name',allowed_fields:'full_name'});
 await applyCorrection(db,digest(token),{revision:4,full_name:'Unsupported 😀',accuracy:'on',processing:'on',consent_version:'1.0'});
 const change=(await db.all("SELECT id FROM gmf_approved_corrections WHERE state='SUBMITTED'"))[0];await assert.rejects(decideApprovedCorrection(db,cfg,'admin',id,{correction_id:change.id,revision:4,action:'approve',verified:'on',reason:'Test rendering failure'}));
 assert.equal((await db.all('SELECT payload FROM gmf_applications WHERE id=?',[id]))[0].payload,before);assert.equal((await db.all('SELECT state FROM gmf_approved_corrections WHERE id=?',[change.id]))[0].state,'SUBMITTED');assert.equal((await db.all('SELECT COUNT(*) AS n FROM gmf_card_revisions'))[0].n,0);
 }finally{await db.close();}});
