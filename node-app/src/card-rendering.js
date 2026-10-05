import PDFDocument from 'pdfkit';
import QRCode from 'qrcode';
import {fileURLToPath} from 'node:url';
import {FormError} from './registration-fields.js';
export const cardWidth=85.6*72/25.4,cardHeight=54*72/25.4;
export const fontPath=fileURLToPath(new URL('../assets/fonts/NotoSansMalayalam-Regular.ttf',import.meta.url));
export const logoPath=fileURLToPath(new URL('../public/img/gramaswaraj-logo.png',import.meta.url));
export const qrPng=url=>QRCode.toBuffer(url,{type:'png',width:600,margin:4,errorCorrectionLevel:'M'});
export const latinFontPath=fileURLToPath(new URL('../assets/fonts/Vera.ttf',import.meta.url));
export function text(doc,value,x,y,width,height,size=8,color='#163747'){
 const runs=word=>word.split(/([\u0d00-\u0d7f\u200c\u200d]+)/u).filter(Boolean).map(value=>({value,font:/[\u0d00-\u0d7f]/u.test(value)?'CardText':'Latin'}));
 const words=String(value).split(/\s+/u).filter(Boolean).map(runs);
 for(const word of words)for(const run of word){doc.font(run.font);for(const ch of run.value)if(!/[\u200c\u200d]/u.test(ch)&&!doc._font.font.hasGlyphForCodePoint(ch.codePointAt(0)))throw new FormError('A card field uses unsupported characters. Configure a suitable card font before issuing.');}
 for(let pts=size;pts>=size-2;pts-=.5){doc.fontSize(pts);const lines=[[]];let used=0,bad=false;doc.font('Latin');const space=doc.widthOfString(' '),leading=pts*1.35;
 for(const word of words){let w=0;for(const run of word){doc.font(run.font);w+=doc.widthOfString(run.value);}if(w>width){bad=true;break;}if(used&&used+space+w>width){lines.push([]);used=0;}lines.at(-1).push({word,width:w});used+=(used?space:0)+w;}
 if(bad||lines.length*leading>height)continue;
 lines.forEach((line,i)=>{let left=x;for(const item of line){for(const run of item.word){doc.font(run.font).fontSize(pts).fillColor(color).text(run.value,left,y+i*leading,{lineBreak:false});left+=doc.widthOfString(run.value);}left+=space;}});return;
 }
 throw new FormError('Card text does not fit the print area. Use a shorter printable name or location.');
}
function draw(doc,s,portrait,qr,back,x=0,y=0){doc.save().translate(x,y);doc.rect(0,0,cardWidth,cardHeight).fill('#ffffff');doc.rect(0,0,cardWidth,31).fill('#12394a');doc.image(logoPath,7,3,{fit:[19,26]});text(doc,(s.brand||'Gramaswaraj').toUpperCase(),32,4,198,14,10,'#ffffff');text(doc,s.network||'Digital Media & Broadcasting Network',32,18,198,10,5.7,'#ffffff');
 if(!back){doc.image(portrait,10,40,{fit:[53,71]});text(doc,'MEDIA FACILITATOR',73,38,157,14,8,'#117d69');text(doc,s.name,73,52,157,27,10);if(s.name_ml)text(doc,s.name_ml,73,81,157,17,8);text(doc,s.number,73,100,157,13,8);text(doc,s.panchayat+' Grama Panchayat',10,116,220,18,7);text(doc,`${s.role} · Valid until ${s.valid_until}`,10,137,220,11,6.5);}
 else{doc.image(qr,8,39,{width:80,height:80});text(doc,'SCAN TO VERIFY CURRENT STATUS',97,40,133,24,7,'#117d69');text(doc,s.panchayat+' Grama Panchayat',97,65,133,25,7);text(doc,`${s.block} Block · ${s.district}`,97,91,133,26,6.5);text(doc,s.card_number,10,120,225,12,6.5);text(doc,`Issued ${s.issued_on} · Scan before accepting this card.`,10,134,225,12,6);}
 if(s.preview&&back)text(doc,'DEVELOPMENT PREVIEW',10,146,220,7,5,'#b00020');
 if(s.preview&&!back){doc.save().opacity(.20).rotate(-18,{origin:[cardWidth/2,cardHeight/2]});text(doc,'DEVELOPMENT PREVIEW',8,68,225,35,17,'#b00020');doc.restore();}
 doc.restore();}
async function pdf(s,portrait,qr,print){return new Promise((resolve,reject)=>{const doc=new PDFDocument({autoFirstPage:false,margin:0,compress:true,info:{Title:'Gramaswaraj Media Facilitator ID Card',Author:'Gramaswaraj'}}),chunks=[];doc.on('data',c=>chunks.push(c));doc.on('error',reject);doc.on('end',()=>resolve(Buffer.concat(chunks)));try{doc.registerFont('CardText',fontPath);doc.registerFont('Latin',latinFontPath);if(print){doc.addPage({size:'A4',margin:0});text(doc,'Print at 100% / actual size. Cut along the card borders.',36,26,520,20,10);draw(doc,s,portrait,qr,false,36,64);draw(doc,s,portrait,qr,true,316,64);doc.strokeColor('#777777').lineWidth(.4).rect(36,64,cardWidth,cardHeight).rect(316,64,cardWidth,cardHeight).stroke();}else{for(const back of [false,true]){doc.addPage({size:[cardWidth,cardHeight],margin:0});draw(doc,s,portrait,qr,back);}}doc.end();}catch(e){doc.destroy();reject(e);}});}
export async function renderCards(snapshot,portrait,url){const qr=await qrPng(url);return {pdf:await pdf(snapshot,portrait,qr,false),print_pdf:await pdf(snapshot,portrait,qr,true)};}
