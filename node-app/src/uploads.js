import {Worker} from 'node:worker_threads';
import {FormError} from './registration-fields.js';
export const maxFileBytes=5*1024*1024;
export function processUpload(file,photo,crop){
 if(!file?.buffer?.length||file.buffer.length>maxFileBytes)throw new FormError('Files must be non-empty and no larger than 5 MB.');
 return new Promise((resolve,reject)=>{
 const worker=new Worker(new URL('./upload-worker.js',import.meta.url),{workerData:{bytes:file.buffer,name:file.originalname,mime:file.mimetype,photo,crop},resourceLimits:{maxOldGenerationSizeMb:128}});
 const timer=setTimeout(()=>{worker.terminate();reject(new FormError('File processing timed out. Use a smaller, simpler file.'));},10000);
 worker.once('message',result=>{clearTimeout(timer);worker.terminate();result.error?reject(new FormError(result.error)):resolve(result);});
 worker.once('error',()=>{clearTimeout(timer);reject(new FormError('Unable to process this file.'));});
 worker.once('exit',code=>{clearTimeout(timer);if(code!==0)reject(new FormError('Unable to process this file.'));});
 });
}
