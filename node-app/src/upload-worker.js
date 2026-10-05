import {parentPort,workerData} from 'node:worker_threads';
import {createHash} from 'node:crypto';
import path from 'node:path';
import sharp from 'sharp';
import {PDFDocument,PDFDict,PDFArray,PDFName,PDFStream,PDFRef} from 'pdf-lib';
sharp.cache(false);sharp.concurrency(1);
try{
 const {name,mime,photo,crop}=workerData;const raw=Buffer.from(workerData.bytes),suffix=path.extname(name).toLowerCase();let output,contentType;
 if(suffix==='.pdf'&&!photo){
 if(!['application/pdf','application/octet-stream'].includes(mime)||raw.subarray(0,5).toString()!=='%PDF-')throw Error('Use a valid PDF.');
 const doc=await PDFDocument.load(raw,{throwOnInvalidObject:true,updateMetadata:false});if(doc.isEncrypted||doc.getPageCount()<1||doc.getPageCount()>30)throw Error('Use an unencrypted PDF with 1–30 pages.');
 const banned=new Set(['JS','JavaScript','Launch','OpenAction','AA','EmbeddedFiles','EF','RichMedia','XFA','AcroForm','GoToR','SubmitForm','ImportData','Rendition','Movie','Sound','FileAttachment','Filespec']);
 const pending=doc.context.enumerateIndirectObjects().map(([,v])=>[v,0]),seen=new Set();let count=0;
 while(pending.length){let [obj,depth]=pending.pop();if(++count>20000||depth>50)throw Error('The PDF is too complex.');if(obj instanceof PDFRef)obj=doc.context.lookup(obj);if(seen.has(obj))continue;seen.add(obj);if(obj instanceof PDFStream)obj=obj.dict;if(obj instanceof PDFDict){for(const [k,v] of obj.entries()){if(banned.has(k.decodeText()))throw Error('PDFs with scripts, forms or embedded files are not allowed.');pending.push([v,depth+1]);}}else if(obj instanceof PDFArray){for(let i=0;i<obj.size();i++)pending.push([obj.get(i),depth+1]);}else if(obj instanceof PDFName&&banned.has(obj.decodeText()))throw Error('This PDF contains unsupported active content.');}
 output=raw;contentType='application/pdf';
 }else{
 if(!['.jpg','.jpeg','.png'].includes(suffix))throw Error('Use JPG, PNG'+(photo?'.':' or PDF.'));
 const expected=suffix==='.png'?'png':'jpeg';if(![`image/${expected}`,'application/octet-stream'].includes(mime))throw Error('The image type does not match its filename.');
 const source=sharp(raw,{limitInputPixels:20000000,failOn:'warning'});const metadata=await source.metadata();if(metadata.format!==expected||(metadata.pages||1)>1||photo&&Math.min(metadata.width,metadata.height)<100)throw Error('Use a valid image of at most 20 megapixels, with a photograph at least 100 pixels on each side.');
 const rotated=await source.rotate().toBuffer({resolveWithObject:true});let image=sharp(rotated.data,{limitInputPixels:20000000});
 if(photo){const [x,y,zoom]=crop;if(![x,y,zoom].every(Number.isFinite)||x<0||x>100||y<0||y>100||zoom<1||zoom>3)throw Error('Invalid photograph crop.');const width=Math.floor(Math.min(rotated.info.width,rotated.info.height*.75)/zoom/3)*3,height=width/3*4;image=image.extract({left:Math.floor((rotated.info.width-width)*x/100),top:Math.floor((rotated.info.height-height)*y/100),width,height}).resize(600,800,{fit:'inside',withoutEnlargement:true});}
 else image=image.resize(2400,2400,{fit:'inside',withoutEnlargement:true});
 output=await image.flatten({background:'#ffffff'}).jpeg({quality:90}).toBuffer();contentType='image/jpeg';
 }
 if(output.length>5*1024*1024)throw Error('The processed file exceeds 5 MB.');
 parentPort.postMessage({body:output.toString('base64'),mime:contentType,sha256:createHash('sha256').update(output).digest('hex')});
}catch(e){parentPort.postMessage({error:e.message?.startsWith('Use ')||e.message?.startsWith('PDF')||e.message?.startsWith('The ')||e.message?.startsWith('Invalid photograph')||e.message?.startsWith('This PDF')?e.message:'Use a valid JPG/PNG image or an unencrypted, non-interactive PDF.'});}
