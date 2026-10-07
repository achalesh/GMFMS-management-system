import {mkdirSync} from 'node:fs';
import path from 'node:path';
export async function database(config){
 if(config.mysql){
  const {default:mysql}=await import('mysql2/promise');
  const url=new URL(config.mysql);
  if(url.protocol!=='mysql:')throw Error('Use a MySQL URL');
  const pool=mysql.createPool({host:url.hostname,port:Number(url.port||3306),user:decodeURIComponent(url.username),password:decodeURIComponent(url.password),database:decodeURIComponent(url.pathname.slice(1)),charset:'utf8mb4',connectionLimit:5,multipleStatements:false,...(config.ssl?{ssl:{rejectUnauthorized:true}}:{})});
  function wrap(conn){return {dialect:'mysql',all:async(sql,args=[])=>{const [rows]=await conn.execute(sql.replaceAll('INSERT OR IGNORE','INSERT IGNORE'),args);return rows;},run:async(sql,args=[])=>{const [r]=await conn.execute(sql.replaceAll('INSERT OR IGNORE','INSERT IGNORE'),args);return r.affectedRows;}};}
  return {...wrap(pool),dialect:'mysql',transaction:async(fn)=>{const c=await pool.getConnection();try{await c.beginTransaction();const result=await fn(wrap(c));await c.commit();return result;}catch(e){await c.rollback();throw e;}finally{c.release();}},close:()=>pool.end()};
 }
 const {DatabaseSync}=await import('node:sqlite');
 if(config.sqlite!==':memory:')mkdirSync(path.dirname(config.sqlite),{recursive:true});
 const db=new DatabaseSync(config.sqlite);db.exec('PRAGMA foreign_keys=ON');db.exec('PRAGMA busy_timeout=5000');
 const raw={all:async(s,a=[])=>db.prepare(s).all(...a),run:async(s,a=[])=>db.prepare(s).run(...a).changes};
 let queue=Promise.resolve();const lock=fn=>{const result=queue.then(fn);queue=result.catch(()=>{});return result;};
 return {dialect:'sqlite',all:(...a)=>lock(()=>raw.all(...a)),run:(...a)=>lock(()=>raw.run(...a)),transaction:fn=>lock(async()=>{db.exec('BEGIN IMMEDIATE');try{const value=await fn(raw);db.exec('COMMIT');return value;}catch(e){db.exec('ROLLBACK');throw e;}}),close:()=>lock(()=>db.close())};
}
