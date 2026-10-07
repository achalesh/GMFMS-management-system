import express from 'express';
import {administrationRoutes} from './administration-routes.js';
import {settings} from './settings.js';
import {schemaVersion} from './schema.js';
import {reportRoutes} from './report-routes.js';
import {publicVerification,staffCards} from './card-routes.js';
import {correctionPublic,lifecycleStaff} from './lifecycle-routes.js';
import {uploadMiddleware,publicRegistration,staffApplications} from './registration-routes.js';
import {FormError} from './registration-fields.js';
import helmet from 'helmet';
import session from 'express-session';
import {fileURLToPath} from 'node:url';
import {randomUUID,randomBytes} from 'node:crypto';
import {DatabaseSessions} from './session-store.js';
import {hashPassword,verifyPassword,csrfToken,validCsrf,budget} from './security.js';
import {loadUser,can} from './policies.js';
export async function createApp(db,cfg){
 const app=express(), dummy=await hashPassword(randomBytes(32).toString('hex'));
 app.disable('x-powered-by');app.set('trust proxy',cfg.proxy);
 app.set('view engine','ejs');app.set('views',fileURLToPath(new URL('../views',import.meta.url)));
 app.use(helmet({referrerPolicy:{policy:'same-origin'},contentSecurityPolicy:{directives:{'upgrade-insecure-requests':cfg.production?[]:null}}}));
 app.use('/static',express.static(fileURLToPath(new URL('../public',import.meta.url)),{dotfiles:'deny'}));
 app.use((req,res,next)=>{res.set('Cache-Control','no-store');next();});
 app.get('/health/live/',(req,res)=>res.json({status:'ok'}));
 app.get('/health/ready/',async(req,res)=>{try{const rows=await db.all('SELECT MAX(version) AS version FROM gmf_schema');if(rows[0]?.version!==schemaVersion)throw Error();await settings(db,'system');res.json({status:'ready'});}catch{res.status(503).json({status:'unavailable'});}});
 app.use(publicVerification(db,cfg));
 app.use(express.urlencoded({extended:false,limit:'32kb',parameterLimit:100}));
 app.use(session({name:'gmf.sid',secret:cfg.secret,store:new DatabaseSessions(db),resave:false,saveUninitialized:false,rolling:true,cookie:{httpOnly:true,secure:cfg.production,sameSite:'lax',maxAge:1800000}}));
 app.use(async(req,res,next)=>{
 res.locals.user=req.session.userId?await loadUser(db,req.session.userId):null;
 res.locals.csrf=csrfToken(req.session);
 res.locals.organization=(await settings(db,'organization')).data;
 res.locals.can=cap=>can(res.locals.user,cap);
 next();
 });
 app.use(uploadMiddleware(db,cfg));
 app.use((req,res,next)=>{
 if(!['GET','HEAD','OPTIONS'].includes(req.method)&&(!validCsrf(req.session,req.body?.csrf)||(req.headers.origin&&req.headers.origin!==cfg.origin)))return res.status(403).send('Invalid form. Reload the page and try again.');
 next();
 });
 const audit=(id,action)=>db.run('INSERT INTO gmf_audit(id,user_id,action,created_at) VALUES (?,?,?,?)',[randomUUID(),id,action,Date.now()]);
 app.get('/accounts/login/',(req,res)=>res.locals.user?res.redirect('/'):res.render('login',{error:''}));
 app.post('/accounts/login/',async(req,res)=>{
 const username=typeof req.body.username==='string'?req.body.username.trim().toLowerCase():'';
 const ipOK=await budget(db,cfg.secret,'login-ip',req.ip,40);
 const nameOK=await budget(db,cfg.secret,'login-name',username.slice(0,150),10);
 if(!ipOK||!nameOK)return res.status(429).render('login',{error:'Too many attempts. Please try again in 15 minutes.'});
 const rows=username.length<=150?await db.all('SELECT * FROM gmf_users WHERE username=?',[username]):[];
 const user=rows[0];const matches=await verifyPassword(req.body.password,user?.password_hash||dummy);
 if(!matches||!user?.active)return res.status(401).render('login',{error:'Invalid username or password.'});
 await new Promise((resolve,reject)=>req.session.regenerate(e=>e?reject(e):resolve()));
 req.session.userId=user.id;csrfToken(req.session);await audit(user.id,'login');
 await new Promise((resolve,reject)=>req.session.save(e=>e?reject(e):resolve()));res.redirect('/');
 });
 app.post('/accounts/logout/',async(req,res)=>{if(res.locals.user)await audit(res.locals.user.id,'logout');await new Promise((resolve,reject)=>req.session.destroy(e=>e?reject(e):resolve()));res.clearCookie('gmf.sid');res.redirect('/accounts/login/');});
 app.use(publicRegistration(db,cfg));
 app.use(correctionPublic(db,cfg));
 app.use((req,res,next)=>res.locals.user?next():res.redirect('/accounts/login/'));
 app.use((req,res,next)=>res.locals.user.must_change&&req.path!=='/accounts/password/'?res.redirect('/accounts/password/'):next());
 app.use(administrationRoutes(db,cfg));
 app.use(staffApplications(db));
 app.use(lifecycleStaff(db,cfg));
 app.use(staffCards(db,cfg));
 app.use(reportRoutes(db,cfg));
 async function locations(user){return (await db.all(`SELECT p.code,p.name,p.name_ml,b.code AS block_code,b.name AS block_name,d.code AS district_code,d.name AS district_name FROM gmf_panchayats p JOIN gmf_blocks b ON b.code=p.block_code JOIN gmf_districts d ON d.code=b.district_code JOIN gmf_states s ON s.code=d.state_code WHERE p.active=1 AND b.active=1 AND d.active=1 AND s.active=1 ORDER BY d.name,b.name,p.name`)).filter(r=>can(user,'locations.view',r));}
 app.get('/locations/',async(req,res)=>{
 if(!can(res.locals.user,'locations.view'))return res.sendStatus(403);
 const all=await locations(res.locals.user),q=typeof req.query.q==='string'?req.query.q.slice(0,100):'';
 const rows=all.filter(r=>[r.name,r.name_ml,r.block_name,r.district_name].some(v=>v.toLowerCase().includes(q.toLowerCase())));
 res.render('locations',{rows,q});
 });
 app.use((req,res)=>res.sendStatus(404));
 app.use((error,req,res,next)=>{if(res.headersSent)return next(error);if(error instanceof FormError)return res.status(error.status).render('form-error',{message:error.message});const incident=randomUUID();const code=typeof error.code==='string'&&/^[A-Z0-9_]{1,60}$/.test(error.code)?error.code:'UNEXPECTED_ERROR';console.error(JSON.stringify({event:'request_failed',incident,method:req.method,route:req.route?.path||'middleware',code,type:error.name==='TypeError'?'TypeError':'Error'}));res.set('X-Request-ID',incident);res.status(error.status===413?413:500).send('Unable to complete the request. Please try again. Reference: '+incident);});
 return app;
}
