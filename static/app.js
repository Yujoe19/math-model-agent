const form=document.getElementById('form'), key=document.getElementById('key'), question=document.getElementById('question');
const statusEl=document.getElementById('status'), message=document.getElementById('message'), answer=document.getElementById('answer');
const activity=document.getElementById('activity'), submit=document.getElementById('submit'), filesInput=document.getElementById('files');
const history=[];
question.addEventListener('input',()=>document.getElementById('count').textContent=`${question.value.length} / 40000`);
document.getElementById('toggle').addEventListener('click',e=>{key.type=key.type==='password'?'text':'password';e.target.textContent=key.type==='password'?'显示':'隐藏';});
document.getElementById('reset').addEventListener('click',()=>{if(submit.disabled)return;history.length=0;question.value='';question.dispatchEvent(new Event('input'));filesInput.value='';activity.replaceChildren();answer.textContent='';message.textContent='';statusEl.textContent='等待开始';document.getElementById('empty').hidden=false;document.getElementById('output').hidden=true;});
document.getElementById('copy').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(answer.textContent);message.textContent='已复制最新答复。';}catch{message.textContent='复制失败，请手动选择文本。';}});
function renderTool(event){
 const details=document.createElement('details');details.className='tool-result';const summary=document.createElement('summary');
 summary.textContent=({search_papers:'论文检索结果',search_web:'网页搜索结果',run_python:'Python 运行结果'})[event.name]||'工具结果';
 const result={...event.result};const pictures=result.artifacts||[];delete result.artifacts;
 const pre=document.createElement('pre');pre.textContent=JSON.stringify({输入:event.arguments,结果:result},null,2);details.append(summary,pre);
 for(const p of pictures){if(typeof p.data!=='string'||p.data.length>610000||!/^[A-Za-z0-9+/=]+$/.test(p.data))continue;const url='data:image/png;base64,'+p.data;const img=document.createElement('img');img.src=url;img.alt='Python 生成的图表';img.className='chart';const a=document.createElement('a');a.href=url;a.download=(p.name||'chart.png').replace(/[^a-zA-Z0-9_.-]/g,'_');a.textContent='下载图表';details.append(img,a);}
 activity.append(details);
}
async function getFiles(){const files=[...filesInput.files];if(files.length>4||files.some(f=>f.size>3*1024*1024)||files.reduce((s,f)=>s+f.size,0)>8*1024*1024)throw new Error('最多 4 个文件，每个不超过 3 MB，总量不超过 8 MB。');return Promise.all(files.map(f=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({name:f.name,data:reader.result.split(',')[1]});reader.onerror=()=>reject(new Error('无法读取文件。'));reader.readAsDataURL(f);})));}
form.addEventListener('submit',async event=>{
 event.preventDefault();const current=question.value.trim();if(!current)return;
 if(history.length>=12){message.textContent='已达到 6 轮对话，请新建对话。';return;}
 if(answer.textContent){const previous=document.createElement('details');previous.className='tool-result';const summary=document.createElement('summary');summary.textContent='上一轮答复';const pre=document.createElement('pre');pre.textContent=answer.textContent;previous.append(summary,pre);activity.append(previous);}
 answer.textContent='';message.textContent='';document.getElementById('empty').hidden=true;document.getElementById('output').hidden=false;submit.disabled=true;statusEl.textContent='准备中';
 try{const files=await getFiles();const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({apiKey:key.value,baseUrl:document.getElementById('base-url').value,model:document.getElementById('model').value,question:current,history,files,vision:document.getElementById('vision').checked,search:document.getElementById('search').checked,webSearch:document.getElementById('web-search').checked,searchApiKey:document.getElementById('search-key').value,execute:document.getElementById('execute').checked})});
  if(!response.ok){const data=await response.json();throw new Error(data.error||'请求失败');}const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',completed=false;
  while(true){const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done});const lines=pending.split('\n');pending=lines.pop();for(const line of lines){if(!line.trim())continue;const data=JSON.parse(line);if(data.type==='progress')message.textContent=data.message;if(data.type==='tool_start')statusEl.textContent=({search_papers:'检索论文',search_web:'搜索网页',run_python:'运行 Python'})[data.name]||'调用工具';if(data.type==='tool_result')renderTool(data);if(data.type==='answer')answer.textContent=data.content;if(data.type==='error')throw new Error(data.message);if(data.type==='done'){completed=true;statusEl.textContent='已完成';message.textContent='';}}if(done)break;}
  if(!completed)throw new Error('连接中断，分析未完成。');history.push({role:'user',content:current},{role:'assistant',content:answer.textContent});question.value='';question.dispatchEvent(new Event('input'));question.placeholder='继续追问，例如：解释刚才的模型假设……';
 }catch(error){statusEl.textContent='未完成';message.textContent=error.message||'请求失败，请重试。';}finally{submit.disabled=false;}
});
