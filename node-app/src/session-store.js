import session from 'express-session';
export class DatabaseSessions extends session.Store{
 constructor(db){super();this.db=db;}
 get(id,callback){this.db.all('SELECT payload FROM gmf_sessions WHERE id=? AND expires_at>?',[id,Date.now()]).then(rows=>callback(null,rows[0]?JSON.parse(rows[0].payload):null)).catch(callback);}
 set(id,value,callback){const expires=Date.now()+1800000;this.db.transaction(async tx=>{await tx.run('DELETE FROM gmf_sessions WHERE id=?',[id]);await tx.run('INSERT INTO gmf_sessions(id,payload,expires_at) VALUES (?,?,?)',[id,JSON.stringify(value),expires]);}).then(()=>callback?.()).catch(e=>callback?.(e));}
 destroy(id,callback){this.db.run('DELETE FROM gmf_sessions WHERE id=?',[id]).then(()=>callback?.()).catch(e=>callback?.(e));}
 touch(id,value,callback){this.db.run('UPDATE gmf_sessions SET expires_at=? WHERE id=?',[Date.now()+1800000,id]).then(()=>callback?.()).catch(e=>callback?.(e));}
}
