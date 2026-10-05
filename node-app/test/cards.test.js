import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import sharp from 'sharp';
import {database} from '../src/database.js';
import {migrate} from '../src/schema.js';
import {seed} from '../src/seed.js';
import {config} from '../src/config.js';
import {cardAction,cardState,verificationToken,lookup,publicProfile,hash} from '../src/cards.js';
import {registrySelect} from '../src/registry.js';
import {createApp} from '../src/app.js';
import {PDFDocument} from 'pdf-lib';
async function setup(){const db=await database({sqlite:':memory:'});await migrate(db);await seed(db);const photo=await sharp({create:{width:300,height:400,channels:3,background:'#7b8e9c'}}).jpeg().toBuffer();await db.run("INSERT INTO gmf_users(id,username,email,password_hash,superuser) VALUES ('admin','admin','admin@example.invalid','unused',1)");await db.run("INSERT INTO gmf_applications(id,number,panchayat_code,payload,full_name,normalized_name,mobile,email,status,submitted_at) VALUES ('app','TEST','G01071',?,'Synthetic QA Applicant','synthetic qa applicant','9876543210','private@example.invalid','APPROVED',0)",[JSON.stringify({2:{name_ml:'പരീക്ഷണ പേര്',address:'PRIVATE ADDRESS'},consent:{public_mobile:true,public_email:true}})]);await db.run("INSERT INTO gmf_uploads(owner_id,slot,mime,body,sha256) VALUES ('app','photo','image/jpeg',?,?)",[photo.toString('base64'),hash(photo)]);await db.run("INSERT INTO gmf_facilitators(id,application_id,number,panchayat_code,full_name,role,valid_until,primary_key,approved_by,approved_at) VALUES ('f','app','GS-MF-TVM-0001','G01071','Synthetic QA Applicant','PRIMARY','2099-01-01','G01071','admin',0)");return db;}
const fget=db=>db.all(registrySelect+" WHERE f.id='f'").then(rows=>rows[0]);
const issue={action:'issue',revision:1,reason:'Synthetic QA generation.'};

test('contact publication requires policy plus consent and hides contacts for outdated cards',async()=>{const db=await setup(),cfg=config({});try{
 const payload={2:{mobile:'9876543210',email:'private@example.invalid'},4:{facebook:'https://example.invalid/profile',instagram:'javascript:alert(1)'},consent:{public_mobile:true,public_email:false,public_social:true}};
 await db.run("UPDATE gmf_applications SET payload=? WHERE id='app'",[JSON.stringify(payload)]);
 const id=await cardAction(db,cfg,'admin','f',issue),token=await verificationToken(db,'f'),card=(await db.all('SELECT * FROM gmf_cards WHERE id=?',[id]))[0];
 assert.equal((await publicProfile(db,await fget(db),cfg,token,card.token)).mobile,undefined);
 await db.run("UPDATE gmf_settings SET payload=? WHERE id='system'",[JSON.stringify({allow_public_mobile:true,allow_public_email:true,allow_public_social:true})]);
 const profile=await publicProfile(db,await fget(db),cfg,token,card.token);assert.equal(profile.mobile,'9876543210');assert.equal(profile.email,undefined);assert.deepEqual(profile.social_profiles,{facebook:'https://example.invalid/profile'});
 await db.run("UPDATE gmf_settings SET payload=? WHERE id='organization'",[JSON.stringify({short_name:'Updated Brand'})]);
 const outdated=await publicProfile(db,await fget(db),cfg,token,card.token);assert.equal(outdated.card.status,'OUTDATED');assert.equal(outdated.mobile,undefined);assert.equal(outdated.social_profiles,undefined);
 }finally{await db.close();}});
test('versioned PDFs, source changes, suspension, revocation, token rotation and download integrity',async()=>{const db=await setup(),cfg=config({});try{
 const id=await cardAction(db,cfg,'admin','f',issue),first=(await db.all('SELECT * FROM gmf_cards WHERE id=?',[id]))[0];assert.equal(await cardState(db,first,await fget(db),cfg),'CURRENT');
 const pdf=await PDFDocument.load(Buffer.from(first.pdf,'base64')),print=await PDFDocument.load(Buffer.from(first.print_pdf,'base64'));assert.equal(pdf.getPageCount(),2);assert(Math.abs(pdf.getPage(0).getWidth()-85.6*72/25.4)<.01);assert.equal(print.getPageCount(),1);
 if(process.env.CARD_QA_OUTPUT==='1'){await mkdir('var',{recursive:true});await writeFile('var/qa-card.pdf',Buffer.from(first.pdf,'base64'));await writeFile('var/qa-print.pdf',Buffer.from(first.print_pdf,'base64'));}
 const download=await cardAction(db,cfg,'admin','f',{action:'download',revision:2,card_id:id,format:'pdf',reason:'QA check.'});assert.equal(hash(download.bytes),first.pdf_hash);
 await db.run("UPDATE gmf_facilitators SET status='SUSPENDED' WHERE id='f'");assert.equal(await cardState(db,first,await fget(db),cfg),'INACTIVE');await assert.rejects(cardAction(db,cfg,'admin','f',{...issue,revision:2}));await db.run("UPDATE gmf_facilitators SET status='ACTIVE',role='ASSISTANT' WHERE id='f'");assert.equal(await cardState(db,first,await fget(db),cfg),'OUTDATED');await assert.rejects(cardAction(db,cfg,'admin','f',{action:'download',revision:2,card_id:id,format:'pdf',reason:'Cannot reprint outdated card.'}));
 const next=await cardAction(db,cfg,'admin','f',{...issue,revision:2});assert.equal((await db.all('SELECT status FROM gmf_cards WHERE id=?',[id]))[0].status,'SUPERSEDED');await assert.rejects(cardAction(db,cfg,'admin','f',{...issue,revision:2}));
 await db.run("UPDATE gmf_cards SET pdf='tampered' WHERE id=?",[next]);await assert.rejects(cardAction(db,cfg,'admin','f',{action:'download',revision:3,card_id:next,format:'pdf',reason:'Integrity failure.'}));
 await cardAction(db,cfg,'admin','f',{action:'revoke',revision:3,card_id:next,reason:'Test revocation.'});const revoked=(await db.all('SELECT * FROM gmf_cards WHERE id=?',[next]))[0];assert.equal(await cardState(db,revoked,await fget(db),cfg),'REVOKED');const revokedProfile=await publicProfile(db,await fget(db),cfg,await verificationToken(db,'f'),revoked.token);assert.equal(revokedProfile.status,'REVOKED');assert.equal(revokedProfile.is_authorized,false);
 const token=await verificationToken(db,'f');await cardAction(db,cfg,'admin','f',{action:'rotate',revision:4,reason:'Lost QR.',confirmed:'on'});assert.equal(await lookup(db,token),null);assert(await lookup(db,await verificationToken(db,'f')));
 }finally{await db.close();}});
test('public verification is allowlisted, cookie-free and fails closed for inactive locations and wrong card tokens',async()=>{const db=await setup(),cfg=config({});let server;try{
 const id=await cardAction(db,cfg,'admin','f',issue),token=await verificationToken(db,'f'),card=(await db.all('SELECT token FROM gmf_cards WHERE id=?',[id]))[0];let profile=await publicProfile(db,await lookup(db,token),cfg,token,card.token);assert(profile.is_authorized);assert.equal(await publicProfile(db,await lookup(db,token),cfg,token,'a'.repeat(64)),null);
 const app=await createApp(db,cfg);server=app.listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));const base=`http://127.0.0.1:${server.address().port}`;const res=await fetch(base+'/api/verify/'+token+'/?card='+card.token);const body=await res.text();assert.equal(res.status,200);assert.equal(res.headers.get('set-cookie'),null);assert.equal(res.headers.get('referrer-policy'),'no-referrer');assert.match(res.headers.get('cache-control'),/no-store/);for(const secret of ['9876543210','private@example.invalid','PRIVATE ADDRESS','payload','sha256','application_id'])assert(!body.includes(secret));
 assert.equal((await fetch(base+'/verify/not-a-token/')).status,404);await db.run("UPDATE gmf_panchayats SET active=0 WHERE code='G01071'");profile=await publicProfile(db,await lookup(db,token),cfg,token,card.token);assert.equal(profile.is_authorized,false);assert.equal(profile.card.status,'INACTIVE');
 }finally{if(server)await new Promise(r=>server.close(r));await db.close();}});
test('card operators cannot rotate/revoke identities or issue outside their jurisdiction',async()=>{const db=await setup(),cfg=config({});try{
 await db.run("INSERT INTO gmf_users(id,username,email,password_hash) VALUES ('operator','operator','operator@example.invalid','unused')");await db.run("INSERT INTO gmf_scopes(id,user_id,role,scope,district_code) VALUES ('scope','operator','ID_CARD_OPERATOR','DISTRICT','KSD')");await assert.rejects(cardAction(db,cfg,'operator','f',issue));await db.run("UPDATE gmf_scopes SET district_code='TVM' WHERE id='scope'");const id=await cardAction(db,cfg,'operator','f',issue);await assert.rejects(cardAction(db,cfg,'operator','f',{action:'revoke',revision:2,card_id:id,reason:'Not permitted.'}));await assert.rejects(cardAction(db,cfg,'operator','f',{action:'rotate',revision:2,confirmed:'on',reason:'Not permitted.'}));
 }finally{await db.close();}});
