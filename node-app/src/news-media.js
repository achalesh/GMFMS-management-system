import path from 'node:path';
import {createHash} from 'node:crypto';
import {processUpload} from './uploads.js';
import {FormError} from './registration-fields.js';
export const maxNewsVideoBytes=10*1024*1024;
export const maxNewsImageBytes=5*1024*1024;
export function mp4Video(buffer){
 const invalid=()=>{throw new FormError('Use a valid MP4 video with H.264 encoding. / H.264 MP4 വീഡിയോ തിരഞ്ഞെടുക്കുക.');};
 function boxes(start,end){const result=[];let cursor=start;while(cursor<end){if(end-cursor<8)invalid();let size=buffer.readUInt32BE(cursor),header=8;const type=buffer.toString('ascii',cursor+4,cursor+8);if(size===1){if(end-cursor<16)invalid();const wide=buffer.readBigUInt64BE(cursor+8);if(wide>BigInt(buffer.length))invalid();size=Number(wide);header=16;}if(size===0)size=end-cursor;if(size<header||cursor+size>end)invalid();result.push({type,start:cursor+header,end:cursor+size});cursor+=size;if(result.length>20000)invalid();}return result;}
 const top=boxes(0,buffer.length),ftyp=top.find(box=>box.type==='ftyp'),moov=top.find(box=>box.type==='moov');
 if(!ftyp||ftyp.end-ftyp.start<8||!moov||!top.some(box=>box.type==='mdat'&&box.end>box.start))invalid();
 const brands=[];for(let offset=ftyp.start;offset+4<=ftyp.end;offset+=4)if(offset!==ftyp.start+4)brands.push(buffer.toString('ascii',offset,offset+4));if(!brands.some(brand=>/^iso[0-9m]$|^mp4[12]$|^avc1$|^dash$|^msdh$/.test(brand)))invalid();
 let video=false;for(const track of boxes(moov.start,moov.end).filter(box=>box.type==='trak')){
 const mdia=boxes(track.start,track.end).find(box=>box.type==='mdia');if(!mdia)continue;const children=boxes(mdia.start,mdia.end),handler=children.find(box=>box.type==='hdlr');if(!handler||handler.end-handler.start<12||buffer.toString('ascii',handler.start+8,handler.start+12)!=='vide')continue;
 const minf=children.find(box=>box.type==='minf');if(!minf)invalid();const stbl=boxes(minf.start,minf.end).find(box=>box.type==='stbl');if(!stbl)invalid();const stsd=boxes(stbl.start,stbl.end).find(box=>box.type==='stsd');if(!stsd||stsd.end-stsd.start<8)invalid();
 for(const entry of boxes(stsd.start+8,stsd.end)){if(!['avc1','avc3'].includes(entry.type)||entry.end-entry.start<78)continue;const avcc=boxes(entry.start+78,entry.end).find(box=>box.type==='avcC');if(avcc&&avcc.end-avcc.start>=7&&buffer[avcc.start]===1)video=true;}
 }
 if(!video)invalid();return true;
}
export async function processNewsMedia(file){
 if(!file?.buffer?.length)throw new FormError('Choose a non-empty image or video.');const extension=path.extname(file.originalname||'').toLowerCase();
 if(file.fieldname==='images'){
 if(!['.jpg','.jpeg','.png'].includes(extension)||file.buffer.length>maxNewsImageBytes)throw new FormError('Images must be JPG/PNG, up to 5 MB each. / ഓരോ ചിത്രവും പരമാവധി 5 MB JPG/PNG ആയിരിക്കണം.');
 const result=await processUpload(file,false,[50,50,1]);return {kind:'IMAGE',mime:'image/jpeg',body:Buffer.from(result.body,'base64'),sha256:result.sha256};
 }
 if(file.fieldname!=='video'||extension!=='.mp4'||!['video/mp4','application/octet-stream'].includes(file.mimetype)||file.buffer.length>maxNewsVideoBytes)throw new FormError('Use one MP4 (H.264) video, up to 10 MB. / പരമാവധി 10 MB MP4 വീഡിയോ ഉപയോഗിക്കുക.');
 mp4Video(file.buffer);return {kind:'VIDEO',mime:'video/mp4',body:file.buffer,sha256:createHash('sha256').update(file.buffer).digest('hex')};
}
export function sendNewsMedia(req,res,media,filename){
 const bytes=Buffer.from(media.body);if(createHash('sha256').update(bytes).digest('hex')!==media.sha256)throw new FormError('Media integrity check failed.');
 res.type(media.mime).set({'Cache-Control':'private, no-store','Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff'});res.attachment(filename);if(req.query.download!=='1')res.set('Content-Disposition',res.get('Content-Disposition').replace(/^attachment/,'inline'));
 const range=req.headers.range;if(!range)return res.set('Content-Length',String(bytes.length)).send(bytes);
 const match=/^bytes=(\d*)-(\d*)$/.exec(range);let start,end;
 if(match&&(match[1]||match[2])){start=match[1]?Number(match[1]):Math.max(0,bytes.length-Number(match[2]));end=match[1]?(match[2]?Math.min(Number(match[2]),bytes.length-1):bytes.length-1):bytes.length-1;}
 if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=bytes.length||end<start)return res.status(416).set('Content-Range','bytes */'+bytes.length).end();
 res.status(206).set({'Content-Range':`bytes ${start}-${end}/${bytes.length}`,'Content-Length':String(end-start+1)}).send(bytes.subarray(start,end+1));
}
