import express from 'express';
import {budget} from './security.js';
import {can} from './policies.js';
import {facilitator} from './registry.js';
import {FormError} from './registration-fields.js';
import {lookup,publicProfile,verificationToken,cardAction,cardState} from './cards.js';
import {qrPng} from './card-rendering.js';
export function publicVerification(db,cfg){const r=express.Router();
 async function serve(req,res){res.set({'Cache-Control':'private, no-store, max-age=0','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow, noarchive'});try{
 if(!await budget(db,cfg.secret,'verification',req.ip,240,3600000))return res.status(429).json({error:'Too many verification requests.'});const f=await lookup(db,req.params.token);if(!f)return res.status(404).json({error:'Verification unavailable.'});
 if(req.path.endsWith('/portrait/')){const photo=(await db.all("SELECT body FROM gmf_uploads WHERE owner_id=? AND slot='photo' AND mime='image/jpeg'",[f.application_id]))[0];if(!photo)return res.sendStatus(404);return res.type('jpg').send(Buffer.from(photo.body,'base64'));}
 const profile=await publicProfile(db,f,cfg,req.params.token,req.query.card);if(!profile)return res.status(404).json({error:'Verification unavailable.'});if(req.path.startsWith('/api/'))return res.json(profile);res.render('verification',{profile});
 }catch{res.status(503).json({error:'Verification temporarily unavailable.'});}}
 r.get('/verify/:token/',serve);r.get('/verify/:token/portrait/',serve);r.get('/api/verify/:token/',serve);return r;}
export function staffCards(db,cfg){const r=express.Router();
 r.get('/facilitators/:id/cards/',async(req,res)=>{const f=await facilitator(db,req.params.id,res.locals.user,'cards.issue'),token=await verificationToken(db,f.id);const cards=await db.all('SELECT id,number,version,status,source_hash,issued_on,valid_until FROM gmf_cards WHERE facilitator_id=? ORDER BY version DESC',[f.id]);for(const card of cards)card.state=await cardState(db,card,f,cfg);const events=await db.all('SELECT action,reason,created_at FROM gmf_card_events WHERE facilitator_id=? ORDER BY created_at DESC',[f.id]);res.render('cards',{f,cards,events,url:token?cfg.origin+'/verify/'+token+'/':null,canChange:can(res.locals.user,'facilitators.change',f)});});
 r.post('/facilitators/:id/cards/',async(req,res)=>{const result=await cardAction(db,cfg,res.locals.user.id,req.params.id,req.body);if(result?.bytes){res.set('Content-Disposition',`attachment; filename="${result.number}-${req.body.format}.pdf"`);return res.type('pdf').send(result.bytes);}res.redirect(`/facilitators/${req.params.id}/cards/`);});
 r.get('/facilitators/:id/qr/',async(req,res)=>{const f=await facilitator(db,req.params.id,res.locals.user,'cards.issue'),token=await verificationToken(db,f.id);if(!token)throw new FormError('Create a verification link first.');res.set('Content-Disposition','attachment; filename="verification-qr.png"');res.type('png').send(await qrPng(cfg.origin+'/verify/'+token+'/'));});return r;}
