const imgIn = document.getElementById('imgIn'), prev = document.getElementById('preview');
imgIn.onchange = () => { const f = imgIn.files[0]; if (f) { prev.src = URL.createObjectURL(f); prev.style.display = 'block'; } };
const rec = document.getElementById('recBtn'), audioIn = document.getElementById('audioIn'), ap = document.getElementById('audioPrev');
let mr, chunks = [];
rec.onclick = async () => {
  if (mr && mr.state === 'recording') { mr.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mr = new MediaRecorder(stream); chunks = [];
    mr.ondataavailable = e => chunks.push(e.data);
    mr.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      const file = new File(chunks, 'vocal.webm', { type: mr.mimeType || 'audio/webm' });
      const dt = new DataTransfer(); dt.items.add(file); audioIn.files = dt.files;
      ap.src = URL.createObjectURL(file); ap.hidden = false; rec.textContent = 'Réenregistrer';
    };
    mr.start(); rec.textContent = '⏹ Arrêter';
  } catch (e) { alert("Micro non autorisé"); }
};
audioIn.onchange = () => { const f = audioIn.files[0]; if (f) { ap.src = URL.createObjectURL(f); ap.hidden = false; } };
