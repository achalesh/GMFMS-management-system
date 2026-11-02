import path from 'node:path';
import {mkdir,open,stat,statfs,rename,unlink,readdir} from 'node:fs/promises';
import {createReadStream,createWriteStream} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {Transform} from 'node:stream';
import {randomUUID,createHash} from 'node:crypto';
import {FormError} from './registration-fields.js';
import {newsAuthor} from './news.js';
import {mp4Video,maxNewsVideoBytes} from './news-media.js';
import {policyLock} from './registration-services.js';
import {auditChange} from './administration.js';
export const newsChunkBytes=8*1024*1024;
const day=86400000,leaseMs=10*60000,uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
export function storageFile(cfg,id,suffix){
 if(!uuid.test(id)||!['part','mp4'].includes(suffix)&&!/^chunk-[a-f0-9-]{36}$/.test(suffix))throw new FormError('Invalid media storage key.');
 const root=path.resolve(cfg.newsMediaDir||'var/news-media'),file=path.resolve(root,id+'.'+suffix);if(!file.startsWith(root+path.sep))throw new FormError('Invalid media path.');return file;
}
export function videoSize(value){if(typeof value!=='number'&&(typeof value!=='string'||!/^\d{1,10}$/.test(value)))throw new FormError('Choose a valid video size.');const size=Number(value);if(!Number.isSafeInteger(size)||size<1||size>maxNewsVideoBytes)throw new FormError('Videos must be no larger than 1 GB (1024 MB). / പരമാവധി 1 GB വീഡിയോ തിരഞ്ഞെടുക്കുക.',413);return size;}
async function root(cfg){const directory=path.resolve(cfg.newsMediaDir||'var/news-media');try{await mkdir(directory,{recursive:true,mode:0o700});}catch{throw new FormError('Private video storage is unavailable. Contact the administrator.',503);}return directory;}
async function owned(db,userId,id){await newsAuthor(db,userId);if(!uuid.test(id))throw new FormError('Video upload unavailable.',404);const row=(await db.all('SELECT * FROM gmf_news_file_uploads WHERE id=? AND user_id=?',[id,userId]))[0];if(!row)throw new FormError('Video upload unavailable.',404);if(row.expires_at<Date.now()&&!['ATTACHED'].includes(row.state)||['EXPIRED','REMOVED','INVALID','PURGED'].includes(row.state))throw new FormError('This upload expired or is invalid. Select the video again.',410);return row;}
export async function cleanupNewsFiles(db,cfg){
 const directory=path.resolve(cfg.newsMediaDir||'var/news-media');const expired=await db.all("SELECT id FROM gmf_news_file_uploads WHERE state NOT IN ('ATTACHED','PURGED') AND expires_at<? AND lease_until<? LIMIT 50",[Date.now(),Date.now()]);if(!expired.length)return;
 let names;try{names=await readdir(directory);}catch{return;}
 for(const {id} of expired){if(!uuid.test(id))continue;const changed=await db.run("UPDATE gmf_news_file_uploads SET state='EXPIRED',lease=NULL,lease_until=0 WHERE id=? AND state<>'ATTACHED' AND expires_at<? AND lease_until<?",[id,Date.now(),Date.now()]);if(!changed)continue;
 let failed=false;for(const name of names.filter(name=>name===id+'.part'||name===id+'.mp4'||name.startsWith(id+'.chunk-'))){const suffix=name.slice(37);if(!['part','mp4'].includes(suffix)&&!/^chunk-[a-f0-9-]{36}$/.test(suffix))continue;try{await unlink(storageFile(cfg,id,suffix));}catch(error){if(error.code!=='ENOENT')failed=true;}}
 if(!failed)await db.run("UPDATE gmf_news_file_uploads SET state='PURGED' WHERE id=? AND state='EXPIRED'",[id]);
 }
}
export async function beginNewsUpload(db,cfg,userId,input){
 const size=videoSize(input.size),name=typeof input.name==='string'?path.basename(input.name.replaceAll('\\','/')):'';
 if(!name||name.length>255||!/^.+\.mp4$/i.test(name)||/[\x00-\x1f]/.test(name))throw new FormError('Choose an MP4 (H.264) video.');
 await newsAuthor(db,userId);await root(cfg);await cleanupNewsFiles(db,cfg);
 return db.transaction(async tx=>{await policyLock(tx);await newsAuthor(tx,userId);const pending=await tx.all("SELECT expected_size,received_size FROM gmf_news_file_uploads WHERE user_id=? AND state IN ('UPLOADING','PROCESSING','READY') AND expires_at>?",[userId,Date.now()]);if(pending.length>=2)throw new FormError('Two video uploads are already pending. Finish or discard one before starting another.',409);
 try{const space=await statfs(cfg.newsMediaDir||'var/news-media'),reservations=(await tx.all("SELECT expected_size,received_size FROM gmf_news_file_uploads WHERE state IN ('UPLOADING','PROCESSING') AND expires_at>?",[Date.now()])).reduce((n,row)=>n+Math.max(0,Number(row.expected_size)-Number(row.received_size)),0);if(Number(space.bavail)*Number(space.bsize)<size+reservations+256*1024*1024)throw new FormError('There is not enough private storage for this video. Contact the administrator.',507);}catch(error){if(error instanceof FormError)throw error;if(!['ENOSYS','ENOTSUP'].includes(error.code))throw new FormError('Cannot check private video storage.',503);}
 const id=randomUUID(),now=Date.now();await tx.run('INSERT INTO gmf_news_file_uploads(id,user_id,original_name,expected_size,expires_at,created_at) VALUES (?,?,?,?,?,?)',[id,userId,name,size,now+day,now]);await auditChange(tx,userId,'news.video_upload_started',id,'Facilitator started a resumable video upload.',{size});return {id,offset:0,size,chunkSize:newsChunkBytes,state:'UPLOADING'};
 });
}
export async function newsUploadStatus(db,userId,id){const row=await owned(db,userId,id);return {id:row.id,offset:Number(row.received_size),size:Number(row.expected_size),state:row.state,chunkSize:newsChunkBytes,newsId:row.attached_news_id};}
export async function receiveNewsChunk(db,cfg,userId,id,offsetValue,source){
 const row=await owned(db,userId,id),offset=Number(offsetValue);if(!Number.isSafeInteger(offset)||offset<0||row.state!=='UPLOADING'||offset!==Number(row.received_size))throw Object.assign(new FormError('Upload offset changed. Resume from the saved position.',409),{offset:Number(row.received_size)});
 const length=Math.min(newsChunkBytes,Number(row.expected_size)-offset);if(length<=0)throw new FormError('All chunks are uploaded. Finalize the video.',409);
 const token=randomUUID(),now=Date.now(),acquired=await db.run("UPDATE gmf_news_file_uploads SET lease=?,lease_until=? WHERE id=? AND user_id=? AND state='UPLOADING' AND received_size=? AND (lease IS NULL OR lease_until<?)",[token,now+leaseMs,row.id,userId,offset,now]);if(!acquired)throw new FormError('Another chunk is still uploading. Please retry.',409);
 const temporary=storageFile(cfg,row.id,'chunk-'+token),partial=storageFile(cfg,row.id,'part');let count=0;
 try{
 await root(cfg);source.setTimeout?.(300000,()=>source.destroy(new Error('Chunk timed out')));
 const limit=new Transform({transform(chunk,encoding,done){count+=chunk.length;if(count>length)return done(new FormError('Upload chunk exceeds its expected size.',413));done(null,chunk);}});
 await pipeline(source,limit,createWriteStream(temporary,{flags:'wx',mode:0o600}));if(count!==length)throw new FormError('This chunk was incomplete. Retry from the saved position.',409);
 if(!await db.run('UPDATE gmf_news_file_uploads SET lease_until=? WHERE id=? AND lease=?',[Date.now()+leaseMs,row.id,token]))throw new FormError('Upload lease changed. Retry.',409);
 let handle;try{handle=await open(partial,'r+');}catch(error){if(error.code!=='ENOENT')throw error;handle=await open(partial,'w+',0o600);}try{if((await handle.stat()).size<offset){await handle.truncate(0);await db.run('UPDATE gmf_news_file_uploads SET received_size=0 WHERE id=? AND lease=?',[row.id,token]);throw Object.assign(new FormError('The partial upload is missing. Resume from the beginning.',409),{offset:0});}await handle.truncate(offset);}finally{await handle.close();}
 await pipeline(createReadStream(temporary),createWriteStream(partial,{flags:'a',mode:0o600}));const durable=await open(partial,'r+');try{await durable.sync();}finally{await durable.close();}
 if(!await db.run('UPDATE gmf_news_file_uploads SET received_size=?,expires_at=?,lease=NULL,lease_until=0 WHERE id=? AND lease=?',[offset+length,Date.now()+day,row.id,token]))throw new FormError('Upload state changed. Check its status before retrying.',409);
 return {id:row.id,offset:offset+length,size:Number(row.expected_size),state:'UPLOADING'};
 }catch(error){if(['ENOSPC','EDQUOT'].includes(error.code))throw new FormError('Private video storage is full. Contact the administrator.',507);throw error;}
 finally{await unlink(temporary).catch(()=>{});await db.run('UPDATE gmf_news_file_uploads SET lease=NULL,lease_until=0 WHERE id=? AND lease=?',[row.id,token]);}
}
export async function validateStoredMp4(file){
 const handle=await open(file,'r');try{const {size}=await handle.stat();videoSize(size);let position=0,count=0,ftyp,moov,mdat=false;
 while(position<size){if(++count>20000||size-position<8)throw new FormError('Invalid MP4 container.');const header=Buffer.alloc(16),read=await handle.read(header,0,Math.min(16,size-position),position);if(read.bytesRead<8)throw new FormError('Invalid MP4 header.');let boxSize=header.readUInt32BE(0),headerSize=8;const type=header.toString('ascii',4,8);if(boxSize===1){if(read.bytesRead<16)throw new FormError('Invalid MP4 header.');const wide=header.readBigUInt64BE(8);if(wide>BigInt(size))throw new FormError('Invalid MP4 box size.');boxSize=Number(wide);headerSize=16;}if(boxSize===0)boxSize=size-position;if(boxSize<headerSize||position+boxSize>size)throw new FormError('Invalid MP4 box.');
 if(type==='mdat'&&boxSize>headerSize)mdat=true;
 if(type==='ftyp'||type==='moov'){if(boxSize>(type==='moov'?8*1024*1024:4096))throw new FormError('Video metadata is too complex. Export a standard H.264 MP4.');const box=Buffer.alloc(boxSize);const result=await handle.read(box,0,boxSize,position);if(result.bytesRead!==boxSize)throw new FormError('Incomplete MP4 metadata.');if(type==='ftyp')ftyp=box;else moov=box;}
 position+=boxSize;
 }
 if(!ftyp||!moov||!mdat)throw new FormError('Use an MP4 with a video track.');const sample=Buffer.from([0,0,0,9,109,100,97,116,1]);mp4Video(Buffer.concat([ftyp,moov,sample]));return size;
 }finally{await handle.close();}
}
export async function finishNewsUpload(db,cfg,userId,id){
 const row=await owned(db,userId,id);if(row.state==='READY')return newsUploadStatus(db,userId,id);if(row.state==='ATTACHED')throw new FormError('This video is already attached to a story.',409);if(Number(row.received_size)!==Number(row.expected_size))throw new FormError('Upload all video chunks before finalizing.',409);
 const token=randomUUID(),now=Date.now();if(!await db.run("UPDATE gmf_news_file_uploads SET state='PROCESSING',lease=?,lease_until=? WHERE id=? AND state IN ('UPLOADING','PROCESSING') AND (lease IS NULL OR lease_until<?)",[token,now+leaseMs,row.id,now]))throw new FormError('The video is still processing. Please retry shortly.',409);
 const partial=storageFile(cfg,row.id,'part'),completed=storageFile(cfg,row.id,'mp4');let file=partial;
 try{
 try{await stat(file);}catch(error){if(error.code!=='ENOENT')throw error;file=completed;}
 const size=await validateStoredMp4(file);if(size!==Number(row.expected_size))throw new FormError('Stored video size differs from the upload size.');
 const hash=createHash('sha256');let renewed=Date.now();for await(const chunk of createReadStream(file)){hash.update(chunk);if(Date.now()-renewed>60000){if(!await db.run('UPDATE gmf_news_file_uploads SET lease_until=? WHERE id=? AND lease=?',[Date.now()+leaseMs,row.id,token]))throw new FormError('Upload processing lease changed.',409);renewed=Date.now();}}const digest=hash.digest('hex');if(!await db.run('UPDATE gmf_news_file_uploads SET lease_until=? WHERE id=? AND lease=?',[Date.now()+leaseMs,row.id,token]))throw new FormError('Upload processing lease changed.',409);
 if(file===partial)await rename(partial,completed);
 if(!await db.run("UPDATE gmf_news_file_uploads SET state='READY',sha256=?,lease=NULL,lease_until=0,expires_at=? WHERE id=? AND lease=?",[digest,Date.now()+day,row.id,token]))throw new FormError('Video upload changed. Check its status.',409);
 return {id:row.id,offset:size,size,state:'READY',chunkSize:newsChunkBytes};
 }catch(error){if(error instanceof FormError){const invalidated=await db.run("UPDATE gmf_news_file_uploads SET state='INVALID',lease=NULL,lease_until=0,expires_at=? WHERE id=? AND lease=?",[Date.now()-1,row.id,token]);if(invalidated){await unlink(partial).catch(()=>{});await unlink(completed).catch(()=>{});}}else await db.run("UPDATE gmf_news_file_uploads SET state='UPLOADING',lease=NULL,lease_until=0 WHERE id=? AND lease=?",[row.id,token]);throw error;}
}
export async function discardNewsUpload(db,cfg,userId,id){const row=await owned(db,userId,id);if(row.state==='ATTACHED')throw new FormError('Remove attached media from the editable story instead.',409);if(!await db.run("UPDATE gmf_news_file_uploads SET state='REMOVED',expires_at=? WHERE id=? AND state<>'ATTACHED' AND (lease IS NULL OR lease_until<?)",[Date.now()-1,row.id,Date.now()]))throw new FormError('The video is still uploading. Try again shortly.',409);await cleanupNewsFiles(db,cfg);}
export async function sendStoredNewsMedia(req,res,db,cfg,media,uploadId,filename){
 const upload=(await db.all("SELECT id,expected_size FROM gmf_news_file_uploads WHERE id=? AND state='ATTACHED' AND attached_news_id=?",[uploadId,media.news_id]))[0];if(!upload)throw new FormError('Video unavailable.',404);const file=storageFile(cfg,upload.id,'mp4'),info=await stat(file);if(info.size!==Number(upload.expected_size)||info.size!==Number(media.size))throw new FormError('Stored video size check failed.');
 let start=0,end=info.size-1;res.type('video/mp4').set({'Cache-Control':'private, no-store','Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff'}).attachment(filename);if(req.query.download!=='1')res.set('Content-Disposition',res.get('Content-Disposition').replace(/^attachment/,'inline'));
 if(req.headers.range){const match=/^bytes=(\d*)-(\d*)$/.exec(req.headers.range);if(!match||!match[1]&&!match[2])return res.status(416).set('Content-Range','bytes */'+info.size).end();start=match[1]?Number(match[1]):Math.max(0,info.size-Number(match[2]));end=match[1]?(match[2]?Math.min(Number(match[2]),info.size-1):info.size-1):info.size-1;if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=info.size||end<start)return res.status(416).set('Content-Range','bytes */'+info.size).end();res.status(206).set('Content-Range',`bytes ${start}-${end}/${info.size}`);}
 res.set('Content-Length',String(end-start+1));if(req.method==='HEAD')return res.end();try{await pipeline(createReadStream(file,{start,end}),res);}catch(error){if(!res.destroyed)res.destroy(error);}
}
