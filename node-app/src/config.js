import path from 'node:path';
import {homedir} from 'node:os';
import {fileURLToPath} from 'node:url';
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
 const sqlite=path.resolve(env.SQLITE_PATH||'var/development.sqlite');
 if(production&&env.NEWS_MEDIA_DIR&&!path.isAbsolute(env.NEWS_MEDIA_DIR))throw Error('NEWS_MEDIA_DIR must be an absolute private persistent path');
 const newsMediaDir=path.resolve(env.NEWS_MEDIA_DIR||(production?path.join(homedir(),'.gramaswaraj','news-media'):path.join(path.dirname(sqlite),'news-media')));
 const appRoot=path.resolve(fileURLToPath(new URL('..',import.meta.url)));
 if(production&&(newsMediaDir===appRoot||newsMediaDir.startsWith(appRoot+path.sep)))throw Error('NEWS_MEDIA_DIR must be outside the versioned application directory');
 if(production&&newsMediaDir.split(/[\\/]/).some(part=>['public_html','htdocs'].includes(part.toLowerCase())))throw Error('News media storage must be outside the public web root');
 return {production,origin:origin.origin,secret,proxy,port,mysql:env.MYSQL_URL,ssl:env.MYSQL_SSL==='true',sqlite,newsMediaDir};
}
