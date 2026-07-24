// ===== Reset password page JS =====
function updatePasswordStrength(pwd){
  const bar=document.getElementById('pwd-strength-bar');
  const txt=document.getElementById('pwd-strength-text');
  if(!bar||!txt)return;
  const hasLen=pwd.length>=8;
  const hasNum=/\d/.test(pwd);
  const hasLetter=/[a-zA-Z]/.test(pwd);
  const reqLen=document.getElementById('req-len');
  const reqNum=document.getElementById('req-num');
  const reqLetter=document.getElementById('req-letter');
  if(reqLen)reqLen.classList.toggle('met',hasLen);
  if(reqNum)reqNum.classList.toggle('met',hasNum);
  if(reqLetter)reqLetter.classList.toggle('met',hasLetter);
  const score=[hasLen,hasNum,hasLetter].filter(Boolean).length;
  bar.className='password-strength-bar '+(score<=1?'weak':score===2?'mid':'strong');
  txt.className='password-strength-text '+(score<=1?'weak':score===2?'mid':'strong');
  txt.textContent=score<=1?'弱':score===2?'中':'强';
}
