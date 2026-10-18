let cart = JSON.parse(localStorage.getItem('cart') || '[]');
let pos = null;
const $ = s => document.querySelector(s);
const save = () => { localStorage.setItem('cart', JSON.stringify(cart)); render(); };

function render() {
  $('#cartCount').textContent = cart.reduce((a, i) => a + i.qty, 0);
  $('#cartItems').innerHTML = cart.map((i, k) =>
    `<div class="row"><div class="grow"><b>${i.name}</b> ${i.size || ''}<br>${i.price} ${CURRENCY} × ${i.qty}</div>
     <button class="pill" onclick="chg(${k},-1)">−</button><button class="pill" onclick="chg(${k},1)">+</button></div>`).join('')
    || '<p class="sub">Panier vide</p>';
  $('#cartTotal').textContent = cart.reduce((a, i) => a + i.price * i.qty, 0);
}
function chg(k, d) { cart[k].qty += d; if (cart[k].qty <= 0) cart.splice(k, 1); save(); }

document.querySelectorAll('.size').forEach(b => b.onclick = () => {
  b.parentElement.querySelectorAll('.size').forEach(x => x.classList.remove('on'));
  b.classList.add('on');
});
document.querySelectorAll('.add').forEach(b => b.onclick = () => {
  const card = b.closest('.card');
  const on = card.querySelector('.size.on');
  if (b.dataset.hassizes === '1' && !on) { alert('Choisis une taille'); return; }
  const size = on ? on.dataset.size : '';
  const ex = cart.find(i => i.id == b.dataset.id && i.size == size);
  if (ex) ex.qty++; else cart.push({ id: +b.dataset.id, name: b.dataset.name, price: +b.dataset.price, size, qty: 1 });
  save(); $('#drawer').classList.add('open');
});
$('#cartBtn').onclick = () => $('#drawer').classList.add('open');
$('#closeCart').onclick = () => $('#drawer').classList.remove('open');

$('#geoBtn').onclick = () => {
  if (!navigator.geolocation) { $('#geoMsg').textContent = 'GPS indisponible'; return; }
  navigator.geolocation.getCurrentPosition(
    p => { pos = { lat: p.coords.latitude, lng: p.coords.longitude }; $('#geoMsg').textContent = '✓ Position partagée'; },
    () => { $('#geoMsg').textContent = 'Position refusée'; });
};
$('#checkout').onsubmit = async e => {
  e.preventDefault();
  if (!cart.length) return alert('Panier vide');
  const f = new FormData(e.target);
  const r = await fetch('/order', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: f.get('name'), phone: f.get('phone'), address: f.get('address'),
      items: cart.map(i => ({ id: i.id, size: i.size, qty: i.qty })), ...(pos || {}) }) });
  const d = await r.json();
  if (!d.ok) return alert(d.error);
  cart = []; save(); $('#drawer').classList.remove('open');
  if (d.whatsapp.includes('wa.me/?')) alert('Commande enregistrée !');
  else window.location = d.whatsapp;
};
render();
