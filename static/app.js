const form = document.getElementById('form');
const key = document.getElementById('key');
const question = document.getElementById('question');
const statusEl = document.getElementById('status');
const message = document.getElementById('message');
const answer = document.getElementById('answer');
const activity = document.getElementById('activity');
const submit = document.getElementById('submit');
question.addEventListener('input', () => document.getElementById('count').textContent = `${question.value.length} / 40000`);
document.getElementById('toggle').addEventListener('click', e => { key.type = key.type === 'password' ? 'text' : 'password'; e.target.textContent = key.type === 'password' ? '显示' : '隐藏'; });
function renderTool(event) {
  const details = document.createElement('details'); details.className = 'tool-result';
  const summary = document.createElement('summary'); summary.textContent = event.name === 'search_papers' ? '论文检索结果' : 'Python 运行结果';
  const pre = document.createElement('pre'); pre.textContent = JSON.stringify({输入: event.arguments, 结果: event.result}, null, 2);
  details.append(summary, pre); activity.append(details);
}
document.getElementById('copy').addEventListener('click', async () => { try { await navigator.clipboard.writeText(answer.textContent); message.textContent='已复制最终答复。'; } catch { message.textContent='复制失败，请手动选择文本。'; } });
form.addEventListener('submit', async event => {
  event.preventDefault(); answer.textContent=''; activity.replaceChildren(); message.textContent=''; document.getElementById('empty').hidden=true; document.getElementById('output').hidden=false; submit.disabled=true; statusEl.textContent='准备中';
  try {
    const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({apiKey:key.value,question:question.value,model:document.getElementById('model').value,search:document.getElementById('search').checked,execute:document.getElementById('execute').checked})});
    if(!response.ok){const data=await response.json();throw new Error(data.error||'请求失败');}
    const reader=response.body.getReader(), decoder=new TextDecoder(); let pending='', completed=false;
    while(true){const {value,done}=await reader.read();pending+=decoder.decode(value||new Uint8Array(),{stream:!done});const lines=pending.split('\n');pending=lines.pop();for(const line of lines){if(!line.trim())continue;const data=JSON.parse(line);if(data.type==='progress')message.textContent=data.message;if(data.type==='tool_start')statusEl.textContent=data.name==='search_papers'?'检索论文':'运行 Python';if(data.type==='tool_result')renderTool(data);if(data.type==='answer')answer.textContent=data.content;if(data.type==='error')throw new Error(data.message);if(data.type==='done'){completed=true;statusEl.textContent='已完成';message.textContent='';}}if(done)break;}
    if(!completed)throw new Error('连接中断，分析未完成。');
  }catch(error){statusEl.textContent='未完成';message.textContent=error.message||'请求失败，请重试。';}finally{submit.disabled=false;}
});
