import {beginNewsUpload,newsUploadStatus,receiveNewsChunk,finishNewsUpload,discardNewsUpload,cleanupNewsFiles,sendStoredNewsMedia} from './news-files.js';
import express from 'express';
import multer from 'multer';
import {randomUUID} from 'node:crypto';
import {budget} from './security.js';
import {FormError} from './registration-fields.js';
import {loadUser,can} from './policies.js';
import {ownFacilitator} from './facilitator-accounts.js';
import {today} from './registry.js';
import {newsStatuses,newsEditable,newsStaff,newsSelectFor,newsAuthor,newsRecord,newsMedia,saveNews,reviewNews} from './news.js';
import {maxNewsDirectVideoBytes,sendNewsMedia} from './news-media.js';
export function newsUploadMiddleware(db,cfg){
 const parse=multer({storage:multer.memoryStorage(),limits:{fileSize:maxNewsDirectVideoBytes,files:4,fields:16,parts:20,fieldSize:100000}}).fields([{name:'images',maxCount:3},{name:'video',maxCount:1}]);let inFlight=0;
 return async(req,res,next)=>{
 if(req.method!=='POST'||!req.is('multipart/form-data')||!/^\/my\/news\/(new|[a-f0-9-]+\/edit)\/?$/.test(req.path))return next();
 if(!res.locals.user?.facilitator_id)return next(new FormError('Sign in with your facilitator account.',403));if(res.locals.user.must_change)return res.redirect('/accounts/password/');
 if(req.headers.origin&&req.headers.origin!==cfg.origin)return res.sendStatus(403);
 await newsAuthor(db,req.session.userId);
 const match=/^\/my\/news\/([a-f0-9-]+)\/edit\/?$/.exec(req.path);if(match){const article=await newsRecord(db,res.locals.user,match[1]);if(!newsEditable.has(article.status))return next(new FormError('This news is being reviewed and cannot be edited.',409));}
 if(inFlight>=2||!await budget(db,cfg.secret,'news-upload',req.session.userId,20,3600000))return next(new FormError('Please wait before uploading again. / കുറച്ച് സമയത്തിന് ശേഷം വീണ്ടും ശ്രമിക്കുക.',429));
 inFlight++;let done=false;const release=()=>{if(!done){done=true;inFlight--;}};res.once('finish',release);res.once('close',release);
 req.newsMultipart=true;parse(req,res,error=>{if(error)req.newsUploadError=new FormError('Attach up to 3 JPG/PNG images (5 MB each). Use the chunked uploader for videos up to 1 GB; direct uploads are limited to 10 MB. Select files again after correcting the form. / ഫയൽ പരിധികൾ പരിശോധിച്ച് വീണ്ടും തിരഞ്ഞെടുക്കുക.',413);next();});
 };
}
export function newsRoutes(db,cfg){const r=express.Router();
 const uploadApi=handler=>async(req,res,next)=>{try{const result=await handler(req,res);if(!res.headersSent&&!res.destroyed)res.json(result||{ok:true});}catch(error){if(res.destroyed||['ECONNRESET','ERR_STREAM_PREMATURE_CLOSE'].includes(error.code))return;if(error instanceof FormError)return res.status(error.status).json({error:error.message,...(error.offset!==undefined?{offset:error.offset}:{})});next(error);}};
 r.post('/my/news/uploads/start/',uploadApi(async req=>{if(!await budget(db,cfg.secret,'news-large-start',req.session.userId,5,3600000))throw new FormError('Please finish existing uploads before starting more.',429);return beginNewsUpload(db,cfg,req.session.userId,req.body);}));
 r.get('/my/news/uploads/:uploadId/',uploadApi(req=>newsUploadStatus(db,req.session.userId,req.params.uploadId)));
 r.put('/my/news/uploads/:uploadId/chunk/',uploadApi(async req=>{if(!await budget(db,cfg.secret,'news-chunk',req.session.userId,2000,3600000))throw new FormError('Please wait before uploading more chunks.',429);return receiveNewsChunk(db,cfg,req.session.userId,req.params.uploadId,req.query.offset,req);}));
 r.post('/my/news/uploads/:uploadId/finish/',uploadApi(req=>finishNewsUpload(db,cfg,req.session.userId,req.params.uploadId)));
 r.delete('/my/news/uploads/:uploadId/',uploadApi(req=>discardNewsUpload(db,cfg,req.session.userId,req.params.uploadId)));

 function list(req,res,rows,status,personal){const raw=req.query.page||'1';if(typeof raw!=='string'||!/^\d{1,6}$/.test(raw))throw new FormError('Choose a valid page.');const total=rows.length,pages=Math.max(1,Math.ceil(total/24)),page=Math.min(pages,Math.max(1,Number(raw)));res.render('news-list',{newsPage:true,rows:rows.slice((page-1)*24,page*24),newsStatuses,status,personal,total,pages,page});}
 const filter=value=>{if(value===undefined)return '';if(typeof value!=='string'||value.length>30||value&&!Object.hasOwn(newsStatuses,value))throw new FormError('Choose a valid news status.');return value;};
 async function form(req,res,error='',values){const {f}=await newsAuthor(db,req.session.userId),article=req.params.id?await newsRecord(db,res.locals.user,req.params.id):null;
 if(article&&!newsEditable.has(article.status))throw new FormError('This news cannot be edited while under review.',409);
 const media=article?await newsMedia(db,article.id):[],initial=article?{...article,hashtags:article.tags.join(' ')}:{programme_date:today(),language:'ML',creation_id:randomUUID()};
 const feedback=article?(await db.all("SELECT note FROM gmf_news_events WHERE news_id=? AND action='review_changes' ORDER BY created_at DESC LIMIT 1",[article.id]))[0]?.note:'';res.render('news-form',{newsPage:true,f,article,media,error,feedback,values:{...initial,...values}});
 }
 r.get('/my/news/',async(req,res)=>{const {f}=await ownFacilitator(db,req.session.userId),status=filter(req.query.status);const rows=await db.all(newsSelectFor(db)+' WHERE n.facilitator_id=? ORDER BY n.updated_at DESC',[f.id]);list(req,res,rows.filter(row=>!status||row.status===status),status,true);});
 r.get('/my/news/new/',async(req,res)=>form(req,res));
 r.get('/my/news/:id/edit/',async(req,res)=>form(req,res));
 async function save(req,res){try{if(req.newsUploadError)throw req.newsUploadError;const files=[...(req.files?.images||[]),...(req.files?.video||[])];const id=await saveNews(db,req.session.userId,req.params.id||null,req.body,files);await cleanupNewsFiles(db,cfg).catch(()=>{});if(req.get('Accept')?.includes('application/json'))return res.status(201).json({redirect:'/my/news/'+id+'/'});res.redirect('/my/news/'+id+'/');}catch(error){if(!(error instanceof FormError))throw error;if(req.get('Accept')?.includes('application/json'))return res.status(error.status).json({error:error.message});if(![400,413].includes(error.status))throw error;res.status(error.status);await form(req,res,error.message,req.body);}}
 r.post('/my/news/new/',save);r.post('/my/news/:id/edit/',save);
 async function detail(req,res,personal){const article=await newsRecord(db,res.locals.user,req.params.id),media=await newsMedia(db,article.id),events=await db.all('SELECT action,to_status,note,created_at FROM gmf_news_events WHERE news_id=? ORDER BY created_at DESC',[article.id]);res.render('news-detail',{newsPage:true,article,media,events,newsStatuses,personal,editable:personal&&newsEditable.has(article.status),mayReview:!personal&&can(res.locals.user,'news.review',article),mediaBase:(personal?'/my/news/':'/news/')+article.id+'/media/'});}
 async function media(req,res){const article=await newsRecord(db,res.locals.user,req.params.id),file=(await db.all('SELECT * FROM gmf_news_media WHERE news_id=? AND id=?',[article.id,req.params.mediaId]))[0];if(!file)throw new FormError('Media unavailable.',404);const filename=article.number+'-'+file.position+(file.kind==='VIDEO'?'.mp4':'.jpg');const stored=(await db.all('SELECT upload_id FROM gmf_news_file_media WHERE media_id=?',[file.id]))[0];if(stored)return sendStoredNewsMedia(req,res,db,cfg,file,stored.upload_id,filename);sendNewsMedia(req,res,file,filename);}
 r.get('/my/news/:id/media/:mediaId',media);r.get('/my/news/:id/',async(req,res)=>detail(req,res,true));
 r.get('/news/',async(req,res)=>{if(!newsStaff(res.locals.user))throw new FormError('News editorial access denied.',403);const status=filter(req.query.status),rows=(await db.all(newsSelectFor(db)+" WHERE n.status<>'DRAFT' ORDER BY n.updated_at DESC")).filter(row=>can(res.locals.user,'news.view',row)&&(!status||row.status===status));list(req,res,rows,status,false);});
 r.get('/news/:id/media/:mediaId',media);r.get('/news/:id/',async(req,res)=>detail(req,res,false));
 r.post('/news/:id/',async(req,res)=>{if(!await budget(db,cfg.secret,'news-review',req.session.userId,100,3600000))throw new FormError('Please try again later.',429);await reviewNews(db,req.session.userId,req.params.id,req.body);res.redirect('/news/'+req.params.id+'/');});
 return r;
}
