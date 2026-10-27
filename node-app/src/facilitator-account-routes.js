import express from 'express';
import {can} from './policies.js';
import {facilitator} from './registry.js';
import {FormError} from './registration-fields.js';
import {budget} from './security.js';
import {provisionFacilitatorAccount,ownFacilitator,ownCard} from './facilitator-accounts.js';
import {cardState,authorization} from './cards.js';
import {auditChange} from './administration.js';
export function facilitatorAccountRoutes(db,cfg){const r=express.Router();
 async function accountPage(req,res,error=''){
 if(!can(res.locals.user,'accounts.manage'))throw new FormError('Account management access denied.',403);
 const f=await facilitator(db,req.params.id,res.locals.user,'accounts.manage'),application=(await db.all('SELECT email FROM gmf_applications WHERE id=?',[f.application_id]))[0];
 const account=(await db.all(`SELECT u.username,u.active,COALESCE(m.revision,1) AS revision FROM gmf_facilitator_accounts fa JOIN gmf_users u ON ${db.dialect==='mysql'?'CAST(u.id AS BINARY)=CAST(fa.user_id AS BINARY)':'u.id=fa.user_id'} LEFT JOIN gmf_account_meta m ON m.id=u.id WHERE fa.facilitator_id=?`,[f.id]))[0];res.render('facilitator-account',{f,account,email:application.email,error});
 }
 r.get('/facilitators/:id/login/',async(req,res)=>accountPage(req,res));
 r.post('/facilitators/:id/login/',async(req,res)=>{
 if(!await budget(db,cfg.secret,'facilitator-account',req.session.userId,20,3600000))throw new FormError('Too many login allocations. Try again later.',429);
 try{const credentials=await provisionFacilitatorAccount(db,req.session.userId,req.params.id,req.body);res.render('facilitator-credentials',{credentials,origin:cfg.origin});}catch(error){if(!(error instanceof FormError)||error.status!==400)throw error;res.status(400);await accountPage(req,res,error.message);}
 });
 r.get('/my/',async(req,res)=>{const profile=await ownFacilitator(db,req.session.userId);const card=(await db.all("SELECT id,number,status,source_hash,valid_until FROM gmf_cards WHERE facilitator_id=? AND status='ISSUED' ORDER BY version DESC LIMIT 1",[profile.f.id]))[0];res.render('facilitator-home',{...profile,status:await authorization(db,profile.f),currentCard:card&&await cardState(db,card,profile.f,cfg)==='CURRENT'?card:null});});
 r.get('/my/photo/',async(req,res)=>{const {f}=await ownFacilitator(db,req.session.userId),photo=(await db.all("SELECT body FROM gmf_uploads WHERE owner_id=? AND slot='photo' AND mime='image/jpeg'",[f.application_id]))[0];if(!photo)throw new FormError('Photo unavailable.',404);res.type('jpg').send(Buffer.from(photo.body,'base64'));});
 r.get('/my/card/preview/',async(req,res)=>{const {bytes}=await ownCard(db,cfg,req.session.userId);res.set('Content-Disposition','inline; filename="My-ID-card.pdf"').type('pdf').send(bytes);});
 r.post('/my/card/',async(req,res)=>{const {bytes,card}=await ownCard(db,cfg,req.session.userId,req.body.format);await auditChange(db,req.session.userId,'facilitator.card_downloaded',card.id,'Facilitator downloaded their own current ID card.',{format:req.body.format});res.attachment(card.number+'.pdf').type('pdf').send(bytes);});
 return r;
}
