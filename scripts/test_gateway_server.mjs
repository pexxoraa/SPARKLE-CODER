// Local integration-test server. Never uses real provider or admin credentials.
import http from 'node:http';
import worker from '../gateway/src/worker.mjs';
import {D1} from '../gateway/tests/helpers.mjs';
const env={DB:new D1(),ADMIN_SECRET:'test-admin-'.repeat(8),CACHE_SECRET:'test-cache-'.repeat(8),NVIDIA_API_KEY:'fake-provider-only',UPI_ID:'test@bank',PAYEE_NAME:'Test Owner',
  UPSTREAM:{fetch:async()=>Response.json({choices:[{message:{role:'assistant',content:'Scripted response'},finish_reason:'stop'}],usage:{prompt_tokens:120,completion_tokens:30}})}};
const server=http.createServer(async(req,res)=>{
  const chunks=[];for await(const chunk of req)chunks.push(chunk);
  const body=Buffer.concat(chunks),origin='http://127.0.0.1:'+server.address().port;
  const response=await worker.fetch(new Request(origin+req.url,{method:req.method,headers:req.headers,...(body.length?{body}:{} )}),env);
  res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
});
server.listen(0,'127.0.0.1',()=>process.stdout.write('http://127.0.0.1:'+server.address().port+'\n'));
