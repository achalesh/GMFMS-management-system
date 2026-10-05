import ExcelJS from 'exceljs';
import PDFDocument from 'pdfkit';
import {fontPath,latinFontPath,logoPath,text} from './card-rendering.js';
import {FormError} from './registration-fields.js';
export const csvSafe=value=>typeof value==='string'&&/^[\s\u0000-\u001f]*[=+@-]/u.test(value)?"'"+value:value;
export function csvBytes(report){const quote=value=>'"'+String(csvSafe(value)??'').replaceAll('"','""')+'"';return Buffer.from('\uFEFF'+[report.headers,...report.rows].map(row=>row.map(quote).join(',')).join('\r\n')+'\r\n','utf8');}
export async function xlsxBytes(report,description){
 const workbook=new ExcelJS.Workbook();workbook.creator='Gramaswaraj';const sheet=workbook.addWorksheet('Report',{views:[{state:'frozen',ySplit:4}]});sheet.properties.defaultRowHeight=20;
 sheet.mergeCells(1,1,1,report.headers.length);sheet.getCell('A1').value=report.title;sheet.getCell('A1').font={name:'Calibri',size:18,bold:true,color:{argb:'FF12394A'}};sheet.getRow(1).height=30;
 sheet.mergeCells(2,1,2,report.headers.length);sheet.getCell('A2').value=description;sheet.getCell('A2').alignment={wrapText:true,vertical:'top'};sheet.getRow(2).height=38;
 sheet.addRow([]);const header=sheet.addRow(report.headers);header.height=26;header.eachCell(cell=>{cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FF12394A'}};cell.font={name:'Calibri',bold:true,color:{argb:'FFFFFFFF'}};cell.alignment={wrapText:true,vertical:'middle'};});
 for(const [index,row] of report.rows.entries()){const added=sheet.addRow(row.map(v=>typeof v==='number'?v:String(v??'')));added.eachCell(cell=>{cell.font={name:'Calibri',size:11};cell.alignment={wrapText:true,vertical:'top'};if(index%2===1)cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FFF0F5F6'}};});}
 sheet.columns.forEach((column,index)=>{const lengths=report.rows.slice(0,200).map(row=>String(row[index]??'').length);column.width=Math.min(44,Math.max(14,report.headers[index].length+2,...lengths.map(n=>n+2)));});for(let r=5;r<=sheet.rowCount;r++){const row=sheet.getRow(r);let lines=1;row.eachCell((cell,index)=>{const value=String(cell.value??'');const units=[...value].reduce((n,ch)=>n+(ch.codePointAt(0)>127?1.6:1),0);lines=Math.max(lines,Math.ceil(units/Math.max(8,sheet.getColumn(index).width-2)));});row.height=Math.max(20,lines*15+4);}
 sheet.autoFilter={from:{row:4,column:1},to:{row:4,column:report.headers.length}};
 sheet.pageSetup={orientation:'landscape',paperSize:9,fitToPage:true,fitToWidth:1,fitToHeight:0};sheet.printTitlesRow='1:4';return Buffer.from(await workbook.xlsx.writeBuffer());
}
export async function pdfBytes(report,description){
 if(report.rows.length>500)throw new FormError('PDF reports support up to 500 rows. Narrow the filters or choose Excel / CSV.');
 return new Promise((resolve,reject)=>{const doc=new PDFDocument({autoFirstPage:false,margin:0,bufferPages:true,info:{Title:'Gramaswaraj — '+report.title,Author:'Gramaswaraj'}}),chunks=[];doc.on('data',c=>chunks.push(c));doc.on('error',reject);doc.on('end',()=>resolve(Buffer.concat(chunks)));
 try{doc.registerFont('CardText',fontPath);doc.registerFont('Latin',latinFontPath);const width=769.89,weights=report.headers.map(h=>/Name|Panchayat|Skills|Equipment/.test(h)?1.5:1),sum=weights.reduce((a,b)=>a+b,0),widths=weights.map(w=>width*w/sum);let y=0,page=0;
 const newPage=()=>{doc.addPage({size:'A4',layout:'landscape',margin:0});page++;doc.image(logoPath,36,20,{fit:[24,33]});text(doc,'GRAMASWARAJ · '+report.title,70,20,730,22,15);text(doc,description,70,46,730,30,7);doc.rect(36,84,width,30).fill('#12394a');let x=36;report.headers.forEach((h,i)=>{text(doc,h,x+4,90,widths[i]-8,23,7,'#ffffff');x+=widths[i];});y=114;};newPage();
 report.rows.forEach((row,index)=>{const height=Math.max(27,Math.min(115,Math.max(...row.map((v,i)=>Math.ceil(String(v??'').length/Math.max(8,(widths[i]-8)/4))*10))+12));if(y+height>550)newPage();if(index%2===1)doc.rect(36,y,width,height).fill('#f0f5f6');let x=36;row.forEach((value,i)=>{text(doc,value??'',x+4,y+6,widths[i]-8,height-10,7);x+=widths[i];});doc.strokeColor('#dde5eb').lineWidth(.3).moveTo(36,y+height).lineTo(36+width,y+height).stroke();y+=height;});if(!report.rows.length)text(doc,'No records match these filters.',36,130,width,25,10);
 const pages=doc.bufferedPageRange();for(let i=0;i<pages.count;i++){doc.switchToPage(i);text(doc,`Permitted jurisdiction only · Page ${i+1} of ${pages.count}`,36,570,width,14,7,'#637988');}doc.end();
 }catch(error){doc.destroy();reject(error instanceof FormError?new FormError('Some report text cannot fit or is unsupported by the PDF fonts. Choose Excel / CSV for the complete data.'):error);}});
}
export async function exportBytes(format,report,description){if(format==='csv')return {bytes:csvBytes(report),mime:'text/csv; charset=utf-8'};if(format==='xlsx')return {bytes:await xlsxBytes(report,description),mime:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'};if(format==='pdf')return {bytes:await pdfBytes(report,description),mime:'application/pdf'};throw new FormError('Choose Excel, CSV or PDF.');}
