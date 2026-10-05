import {randomBytes,scrypt as scryptCallback,pbkdf2 as pbkdf2Callback,timingSafeEqual,createHmac} from 'node:crypto';
import {promisify} from 'node:util';
const scrypt=promisify(scryptCallback),pbkdf2=promisify(pbkdf2Callback);
export async function hashPassword(password){
 if(typeof password!=='string'||password.length<12||password.length>256)throw Error('Password must contain 12–256 characters');
 const salt=randomBytes(16).toString('hex');const key=await scrypt(password,salt,64);
 return `scrypt$${salt}$${key.toString('hex')}`;
}
export async function verifyPassword(password,encoded){
 if(typeof password!=='string'||password.length>256||typeof encoded!=='string')return false;
 try{const [algorithm,a,b,c]=encoded.split('$');let actual,expected;
 if(algorithm==='scrypt'&&/^[a-f0-9]{32}$/.test(a)&&/^[a-f0-9]{128}$/.test(b)){actual=await scrypt(password,a,64);expected=Buffer.from(b,'hex');}
 else if(algorithm==='pbkdf2_sha256'&&Number.isInteger(Number(a))&&Number(a)>=10000&&Number(a)<=3000000&&b.length<=128){actual=await pbkdf2(password,b,Number(a),32,'sha256');expected=Buffer.from(c,'base64');}
 else return false;
 return actual.length===expected.length&&timingSafeEqual(actual,expected);
 }catch{return false;}
}
export function csrfToken(session){return session.csrf ||= randomBytes(32).toString('hex');}
export function validCsrf(session,value){return typeof value==='string'&&/^[a-f0-9]{64}$/.test(value)&&typeof session.csrf==='string'&&/^[a-f0-9]{64}$/.test(session.csrf)&&timingSafeEqual(Buffer.from(value),Buffer.from(session.csrf));}
export async function budget(db,secret,category,identity,limit,window=900000){
 const bucket=Math.floor(Date.now()/window);const id=createHmac('sha256',secret).update(`${category}:${identity}:${bucket}`).digest('hex');
 await db.run('INSERT OR IGNORE INTO gmf_budgets(id,hits,expires_at) VALUES (?,0,?)',[id,(bucket+1)*window]);
 return (await db.run('UPDATE gmf_budgets SET hits=hits+1 WHERE id=? AND hits<?',[id,limit]))===1;
}
