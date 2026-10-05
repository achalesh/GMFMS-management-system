import path from 'node:path';
import {randomBytes} from 'node:crypto';
export function config(env=process.env){
 const production=env.NODE_ENV==='production';
 const origin=new URL(env.APP_ORIGIN || 'http://127.0.0.1:3000');
 if(origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw Error('APP_ORIGIN must be an origin only');
 if(!['http:','https:'].includes(origin.protocol))throw Error('Invalid origin protocol');
 const secret=env.SESSION_SECRET || (production?'':randomBytes(48).toString('hex'));
 if(production && (origin.protocol!=='https:'||secret.length<50||!env.MYSQL_URL))throw Error('Production requires HTTPS, MySQL and a strong session secret');
 const proxy=Number(env.TRUST_PROXY_HOPS||0);
 if(!Number.isInteger(proxy)||proxy<0||proxy>2)throw Error('Invalid proxy hop count');
 const port=Number(env.PORT||3000);
 if(!Number.isInteger(port)||port<0||port>65535)throw Error('Invalid port');
 return {production,origin:origin.origin,secret,proxy,port,mysql:env.MYSQL_URL,ssl:env.MYSQL_SSL==='true',sqlite:path.resolve(env.SQLITE_PATH||'var/development.sqlite')};
}
