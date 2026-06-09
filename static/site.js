/* â•â• EmailJS CONFIG â•â•
       STEP 1: Sign up free at https://www.emailjs.com
       STEP 2: Add Gmail service â†’ copy Service ID below
       STEP 3: Create email template â†’ copy Template ID below
       STEP 4: Go to Account â†’ copy Public Key below
       Full setup guide in README below the HTML file.
    â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */
    document.addEventListener("DOMContentLoaded", function() {
      (function(){
        var EMAILJS_PUBLIC_KEY  = 'YOUR_PUBLIC_KEY';   // <-- paste here
        var EMAILJS_SERVICE_ID  = 'YOUR_SERVICE_ID';   // <-- paste here
        var EMAILJS_TEMPLATE_ID = 'YOUR_TEMPLATE_ID';  // <-- paste here

        window._EJSCONFIG = {
          publicKey:  EMAILJS_PUBLIC_KEY,
          serviceId:  EMAILJS_SERVICE_ID,
          templateId: EMAILJS_TEMPLATE_ID,
          ready: (EMAILJS_PUBLIC_KEY !== 'YOUR_PUBLIC_KEY')
        };

        if (window._EJSCONFIG.ready) {
          emailjs.init({ publicKey: EMAILJS_PUBLIC_KEY });
        }
      })();
    });

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// BANNER CAROUSEL ENGINE
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  const TOTAL      = 5;
  const AUTO_DELAY = 5500;
  const DARK_SLIDES = [2]; // slide 3 has dark city background
  const OFFSCREEN_RIGHT = 'translate3d(104%,0,0)';
  const OFFSCREEN_LEFT = 'translate3d(-104%,0,0)';
  const ONSCREEN = 'translate3d(0,0,0)';

  let current   = 0;
  let autoTimer = null;
  let progTimer = null;
  let progVal   = 0;
  let animating = false;
  let isPaused  = false;
  let isHovering = false;
  let pausedAt  = 0; 

  const slides   = Array.from(document.querySelectorAll('.banner-slide'));
  const dots     = Array.from(document.querySelectorAll('.carousel-dot'));
  const counter  = document.getElementById('carouselCounter');
  const progress = document.getElementById('carouselProgress');
  const curDot   = document.getElementById('cur-dot');
  const curRing  = document.getElementById('cur-ring');

  function pad(n){ return String(n+1).padStart(2,'0'); }

  // Place all non-active slides off-screen to the right on init
  slides.forEach((s,i)=>{
    if(i !== 0) s.style.transform = OFFSCREEN_RIGHT;
  });

  function goTo(next, dir){
    if(animating) return;
    next = ((next % TOTAL) + TOTAL) % TOTAL;
    if(next === current) return;
    animating = true;

    const prev = current;
    current    = next;
    // direction: 1=forward(rightâ†’left), -1=back(leftâ†’right)
    const incoming = dir === -1 ? OFFSCREEN_LEFT : OFFSCREEN_RIGHT;
    const outgoing = dir === -1 ? OFFSCREEN_RIGHT : OFFSCREEN_LEFT;

    // Snap incoming into position (no transition)
    slides[current].style.transition = 'none';
    slides[current].style.transform  = incoming;
    void slides[current].offsetWidth; // force reflow

    // Animate both simultaneously
    slides[current].style.transition = 'transform 0.65s cubic-bezier(0.77,0,0.175,1)';
    slides[current].style.transform  = ONSCREEN;
    slides[prev].style.transition    = 'transform 0.65s cubic-bezier(0.77,0,0.175,1)';
    slides[prev].style.transform     = outgoing;

    // Update z-index so incoming is on top
    slides[current].style.zIndex = '2';
    slides[prev].style.zIndex    = '1';

    // Unlock after animation
    setTimeout(()=>{
      // Reset prev to right (ready for next forward nav)
      slides[prev].style.transition = 'none';
      slides[prev].style.transform  = OFFSCREEN_RIGHT;
      slides[prev].style.zIndex     = '';
      slides[current].style.zIndex  = '';
      animating = false;
    }, 680);

    // Update dots and slides
    dots.forEach((d,i) => d.classList.toggle('active', i === current));
    slides.forEach((s,i) => s.classList.toggle('active', i === current));

    // Update counter
    if(counter) counter.textContent = pad(current) + ' / ' + pad(TOTAL-1);

    // Arrow colour for dark slides
    const isDark = DARK_SLIDES.includes(current);
    document.querySelectorAll('.carousel-arrow').forEach(a=>{
      a.style.background   = isDark ? 'rgba(30,26,18,0.8)' : 'rgba(248,247,243,0.9)';
      a.style.color        = isDark ? 'var(--gold)'        : 'var(--ink)';
      a.style.borderColor  = isDark ? 'rgba(212,168,83,0.3)' : 'var(--smoke)';
    });

    // Nav light/dark state â€” read from slide data-nav attribute
    updateNavState(slides[current]);

    resetProgress();
  }

  function resetProgress(startTimeOffset = 0){
    progVal = (startTimeOffset / AUTO_DELAY) * 100;
    if(progress) progress.style.width = progVal + '%';
    cancelAnimationFrame(progTimer);
    
    const start = performance.now() - startTimeOffset;
    function progStep(now) {
      if(isPaused) {
        pausedAt = now - start;
        return;
      }
      const elapsed = now - start;
      progVal = (elapsed / AUTO_DELAY) * 100;
      if(progress) progress.style.width = Math.min(progVal, 100) + '%';
      if(progVal < 100) {
        progTimer = requestAnimationFrame(progStep);
      } else {
        // Transition to next slide handled by autoTimer setInterval
      }
    }
    progTimer = requestAnimationFrame(progStep);
  }

  function startAuto(resume = false){
    isPaused = false;
    clearInterval(autoTimer);
    clearTimeout(autoTimer);
    
    const remaining = AUTO_DELAY - (resume ? pausedAt : 0);
    
    autoTimer = setTimeout(()=>{ 
      goTo(current + 1, 1); 
      pausedAt = 0;
      // Start regular cycle
      autoTimer = setInterval(()=>{ goTo(current + 1, 1); }, AUTO_DELAY);
    }, remaining);

    resetProgress(resume ? pausedAt : 0);
  }
  function stopAuto(){
    isPaused = true;
    clearInterval(autoTimer);
    clearTimeout(autoTimer);
    cancelAnimationFrame(progTimer);
  }

  // Expose globally
  window.carouselMove = (dir)=>{ 
    stopAuto(); 
    goTo(current + dir, dir); 
    if(!isHovering) startAuto(); 
  };
  window.carouselGoTo = (idx)=>{ 
    stopAuto(); 
    goTo(idx, idx >= current ? 1 : -1); 
    if(!isHovering) startAuto(); 
  };

  // Touch swipe
  let tx = 0;
  const carousel = document.querySelector('.banner-carousel');
  if(carousel){
    carousel.addEventListener('touchstart', e=>{ tx = e.touches[0].clientX; }, {passive:true});
    carousel.addEventListener('touchend',   e=>{
      const diff = tx - e.changedTouches[0].clientX;
      if(Math.abs(diff) > 50) window.carouselMove(diff > 0 ? 1 : -1);
    }, {passive:true});
    carousel.addEventListener('mouseenter', ()=>{ 
      isHovering = true;
      stopAuto(); 
    });
    carousel.addEventListener('mouseleave', ()=>{ 
      isHovering = false;
      startAuto(true); 
    });
  }

  // Keyboard
  document.addEventListener('keydown', e=>{
    if(e.key==='ArrowLeft')  window.carouselMove(-1);
    if(e.key==='ArrowRight') window.carouselMove(1);
  });

  // â”€â”€ Nav state updater â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  window.updateNavState = function(slide){
    const nav = document.getElementById('mainNav');
    if(!nav) return;
    const navMode = slide ? slide.getAttribute('data-nav') : 'light';
    // If user has scrolled, nav is always in scrolled/light state â€” don't interfere
    if(nav.classList.contains('scrolled')) return;
    if(navMode === 'dark'){
      nav.classList.add('dark-nav');
      nav.classList.remove('light-nav');
    } else {
      nav.classList.add('light-nav');
      nav.classList.remove('dark-nav');
    }
  };

  // Boot
  updateNavState(slides[0]); // init nav on first slide
  startAuto();
})();



// Nav scroll â€” throttled with rAF
let rafScroll = 0;
window.addEventListener('scroll',()=>{
  if(rafScroll) return;
  rafScroll = requestAnimationFrame(()=>{
    const nav = document.getElementById('mainNav');
    const isScrolled = window.scrollY > 50;
    nav.classList.toggle('scrolled', isScrolled);
    if(isScrolled){
      nav.classList.remove('light-nav','dark-nav');
    } else {
      const activeSlide = document.querySelector('.banner-slide.img-slide.active');
      if(typeof window.updateNavState === 'function') window.updateNavState(activeSlide);
    }
    rafScroll = 0;
  });
}, {passive:true});

// Scroll reveal
const io = new IntersectionObserver(entries=>{
  entries.forEach(e=>{ if(e.isIntersecting) e.target.classList.add('up'); });
}, {threshold:0.1});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

// â”€â”€ Slide CTA â†’ specific consultation form tab â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function scrollToConsult(tab) {
  // Scroll to #register section
  const reg = document.getElementById('register');
  if(reg) reg.scrollIntoView({behavior:'smooth', block:'start'});
  // Switch form tab after a short delay (let scroll start)
  setTimeout(() => { if(typeof switchTab === 'function') switchTab(tab); }, 320);
}

// Tabs
function switchTab(t){
  // Switch tab buttons
  const tabs = document.querySelectorAll('.ftab');
  const map  = {retail:0, project:1, scale:2, ocean:3, institutional:4};
  tabs.forEach((tab,i) => tab.classList.toggle('active', i === map[t]));
  // Switch panels
  document.querySelectorAll('.fpanel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById('tab-'+t);
  if(panel) panel.classList.add('active');
}

function openConsultModal(tab) {
  const regSection = document.getElementById('register');
  if (regSection) {
    regSection.scrollIntoView({ behavior: 'smooth' });
    if (tab) switchTab(tab);
  }
}


// â”€â”€ Hamburger menu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function isValidPhone(num) {
  // Must be 10 digits and start with 6-9
  return /^[6-9]\d{9}$/.test(num.replace(/\D/g, ''));
}
(function(){
  const btn     = document.getElementById('hamburgerBtn');
  const overlay = document.getElementById('navOverlay');
  const links   = document.querySelector('.nav-links');
  if(!btn) return;

  function openMenu(){
    btn.classList.add('open');
    overlay.classList.add('open');
    links.classList.add('mobile-open');
  }
  function closeMenu(){
    btn.classList.remove('open');
    overlay.classList.remove('open');
    links.classList.remove('mobile-open');
  }

  btn.addEventListener('click', ()=>{
    btn.classList.contains('open') ? closeMenu() : openMenu();
  });
  overlay.addEventListener('click', closeMenu);
  links.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// FORM VALIDATION + SEND CHOICE MODAL
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

/* Pending payload â€” stored after validation, used when user picks channel */
let _pendingWA       = '';
let _pendingEmail    = '';
let _pendingSubj     = '';
let _pendingFormType = 'retail'; // tracks which form submitted
let _pendingEmailData = null;

/* Smart Phone Number Masking (XXXXX XXXXX) */
document.addEventListener('input', function(e) {
  if (e.target && e.target.type === 'tel') {
    var input = e.target;
    var value = input.value.replace(/\D/g, '');
    if (value.length > 10) value = value.slice(0, 10);
    
    var formatted = '';
    if (value.length > 5) {
      formatted = value.slice(0, 5) + ' ' + value.slice(5);
    } else {
      formatted = value;
    }
    
    // Only update if changed to avoid cursor jumps
    if (input.value !== formatted) {
      input.value = formatted;
    }
  }
});

/* Validate Indian PAN Card */
function isValidPAN(pan) {
  return /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(pan.toUpperCase());
}

/* Validate Email more strictly */
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/* Normalise phone â€” ensure + prefix */
function normalisePhone(raw) {
  let p = raw.trim().replace(/\s+/g, '');
  if (p.startsWith('00')) p = '+' + p.slice(2);
  if (p.startsWith('+'))  return p;
  return '+91' + p; // default fallback
}

/* Show inline error */
function showError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = 'âš  ' + msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 5000);
}

/* Open / close modal */
function openSendModal()  {
  document.getElementById('sendModal').classList.add('open');
}
function closeSendModal() {
  document.getElementById('sendModal').classList.remove('open');
  _pendingWA = ''; _pendingEmail = ''; _pendingSubj = ''; _pendingEmailData = null;
}

/* Close modal on overlay click */
document.getElementById('sendModal')?.addEventListener('click', function(e){
  if (e.target === this) closeSendModal();
});

/* Show toast + reset form */
function showSuccess(type) {
  showToast('Thank you! A WhiteFlows advisor will reach out within 24 hours.');
  resetForm(type);
}

/* Toast notification */
function showToast(msg) {
  var existing = document.getElementById('wf-toast');
  if (existing) existing.remove();
  var toast = document.createElement('div');
  toast.id = 'wf-toast';
  toast.textContent = msg;
  toast.style.cssText = 'position:fixed;bottom:32px;left:50%;transform:translateX(-50%);background:#1A1714;color:#D4A853;border:1px solid #D4A853;border-radius:6px;padding:14px 28px;font-family:Raleway,sans-serif;font-size:14px;font-weight:600;letter-spacing:0.04em;z-index:99999;box-shadow:0 8px 32px rgba(0,0,0,0.4);max-width:90vw;text-align:center;opacity:0;transition:opacity 0.3s ease';
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '1'; }, 10);
  const API_BASE_URL = "https://whiteflows.amburax.workers.dev";
  setTimeout(() => { toast.remove(); }, 4000);
}

/* Reset form back to blank state */
function resetForm(type) {
  const panel = document.getElementById('tab-' + type);
  if (panel) {
    // Clear all inputs, selects, and textareas
    panel.querySelectorAll('input, select, textarea').forEach(el => {
      if (el.type === 'checkbox' || el.type === 'radio') {
        el.checked = false;
      } else {
        el.value = '';
      }
    });
    // Reset any select to first option
    panel.querySelectorAll('select').forEach(s => s.selectedIndex = 0);
    panel.style.display = '';
    // Clear loading state from any submit button in this panel
    panel.querySelectorAll('.fsubmit, .reg-submit-btn').forEach(btn => {
      btn.disabled = false;
      btn.classList.remove('loading');
    });
  }
}

/* User chose WhatsApp */
function doSendWhatsApp() {
  if (!isWAscheduled()) {
    showToast('Consultation available Monâ€“Sat 9AMâ€“6PM IST.');
    return;
  }
  if (!_pendingWA) return;

  const btn = document.querySelector('.send-btn-wa');
  if (btn) {
    btn.disabled = true;
    btn.classList.add('loading');
    const label = btn.querySelector('.send-btn-label');
    if (label) label.textContent = 'Processing...';
  }

  window._wfSubmitting = true;
  window.open('https://wa.me/919409272672?text=' + _pendingWA, '_blank');
  
  // Minimal delay before closing to show the "Opening" state
  setTimeout(() => {
    closeSendModal();
    showToast('Opening WhatsApp - we will reply shortly!');
    resetForm(_pendingFormType);
  }, 600);
}

/* User chose Email - sends via server */
function doSendEmail(customBtn) {
  if (!_pendingEmailData) return;
  
  var formType   = _pendingFormType;
  var emailData  = _pendingEmailData;

  // Target the provided button or fall back to the Lead Modal button
  const btn = customBtn || document.querySelector('.send-btn-email');
  if (btn) {
    btn.disabled = true;
    btn.classList.add('loading');
  }

  var leadUrl = 'https://whiteflows.amburax.workers.dev/submit-lead';
  
  fetch(leadUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(emailData)
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Server error ' + res.status);
    return res.json();
  })
  .then(function() {
    showToast('Enquiry sent! We will contact you within 24 hours.');
    closeSendModal();
    resetForm(formType);
  })
  .catch(function(err) {
    console.error('Lead email error:', err);
    
    var isRateLimit = err.message.includes('429');
    var title = isRateLimit ? 'Security Limit Reached' : 'Connection Error';
    var msg = isRateLimit 
      ? 'To protect our premium infrastructure, we limit submissions to 4 per hour. Please try again shortly.'
      : 'Could not connect to our secure server. Please ensure your internet is stable and try again.';
    
    showSecurityModal(title, msg);
    
    // Reset button state on error
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('loading');
      const label = btn.querySelector('.send-btn-label');
      if (label) label.textContent = 'Email';
    }
  });
}

function showSecurityModal(title, message) {
  var overlay = document.getElementById('secOverlay');
  var titleEl = document.getElementById('secTitle');
  var msgEl   = document.getElementById('secMsg');
  if (!overlay || !titleEl || !msgEl) return;
  
  titleEl.textContent = title;
  msgEl.textContent   = message;
  overlay.style.display = 'flex'; setTimeout(function() { overlay.classList.add('active'); }, 10);
  document.body.style.overflow = 'hidden';
}

function closeSecurityModal() {
  var overlay = document.getElementById('secOverlay');
  if (overlay) { overlay.classList.remove('active'); setTimeout(function() { overlay.style.display = 'none'; }, 400); }
  document.body.style.overflow = '';
}

document.addEventListener('DOMContentLoaded', () => {

  /* â”€â”€ Phone Masking (XXXXX XXXXX) â”€â”€ */
  document.querySelectorAll('input[type="tel"]').forEach(inp => {
    inp.addEventListener('input', (e) => {
      let v = e.target.value.replace(/\D/g, '').substring(0, 10);
      if (v.length > 5) e.target.value = v.substring(0, 5) + ' ' + v.substring(5);
      else e.target.value = v;
    });
  });

  /* â”€â”€ Smart Email Suggester (Dynamic @ Triggers) â”€â”€ */
  const emailDomains = ['gmail.com', 'outlook.com', 'yahoo.com', 'icloud.com', 'hotmail.com'];
  const emailDatalist = document.getElementById('email-domains');
  document.querySelectorAll('input[type="email"]').forEach(inp => {
    inp.addEventListener('input', (e) => {
      const val = e.target.value;
      if (val.includes('@')) {
        const parts = val.split('@');
        const local = parts[0];
        const domainPart = parts[1];
        if (local && emailDatalist) {
          emailDatalist.innerHTML = '';
          emailDomains.forEach(d => {
            if (d.startsWith(domainPart)) {
              const opt = document.createElement('option');
              opt.value = local + '@' + d;
              emailDatalist.appendChild(opt);
            }
          });
        }
      } else if (emailDatalist) {
        emailDatalist.innerHTML = '';
      }
    });
    // Prevent showing domains on focus until @ is typed
    inp.addEventListener('focus', (e) => {
      if (emailDatalist && !e.target.value.includes('@')) emailDatalist.innerHTML = '';
    });
  });
});

/* â”€â”€ RETAIL FORM â”€â”€ */
function submitRetail() {
  const fname     = (document.getElementById('r-fname')?.value     || '').trim();
  const lname     = (document.getElementById('r-lname')?.value     || '').trim();
  const email     = (document.getElementById('r-email')?.value     || '').trim();
  const phoneCode = (document.getElementById('r-phone-code')?.value || '+91').trim();
  const phoneNum  = (document.getElementById('r-phone')?.value      || '').trim();
  const phoneRaw  = phoneNum ? (phoneCode + ' ' + phoneNum) : '';
  const country   = (document.getElementById('r-country')?.value   || '').trim();
  const state    = (document.getElementById('r-state')?.value     || '').trim();
  const city     = (document.getElementById('r-city')?.value      || '').trim();
  const invest   = (document.getElementById('r-invest')?.value    || '').trim();
  const horizon  = (document.getElementById('r-horizon')?.value   || '').trim();
  const obj      = (document.getElementById('r-objective')?.value || '').trim();

  if (!fname)                                          { showError('r-error','Please enter your first name.');        return; }
  if (!lname)                                          { showError('r-error','Please enter your last name.');         return; }
  if (!email || !isValidEmail(email))                  { showError('r-error','Please enter a valid email address.');  return; }
  if (!phoneNum || !isValidPhone(phoneNum))
                                                       { showError('r-error','Please enter a valid 10-digit mobile number.'); return; }
  if (!country)                                        { showError('r-error','Please enter your country.'); return; }
  if (!state)                                          { showError('r-error','Please enter your state.'); return; }
  if (!city)                                           { showError('r-error','Please enter your city.'); return; }
  if (!invest)                                         { showError('r-error','Please select your investment range.'); return; }
  if (!horizon)                                        { showError('r-error','Please select your time horizon.');     return; }
  if (!obj)                                            { showError('r-error','Please select your primary objective.'); return; }

  const phone = normalisePhone(phoneRaw);

  _pendingWA = encodeURIComponent(
`*New WhiteFlows Lead â€” Consult*
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Investment Range: ${invest}
Time Horizon: ${horizon}
Objective: ${obj}
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Submitted via WhiteFlows Website`);

  _pendingEmail = encodeURIComponent(
`New WhiteFlows Lead â€” Consult

Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Investment Range: ${invest}
Time Horizon: ${horizon}
Objective: ${obj}

Submitted via WhiteFlows Website`);

  _pendingSubj     = encodeURIComponent('CONSULT LEAD â€” ' + fname + ' ' + lname);
  _pendingFormType = 'retail';
  _pendingEmailData = { 
    type: 'retail', 
    form_name: 'Retail/HNI Consult',
    subject: decodeURIComponent(_pendingSubj),
    name: `${fname} ${lname}`,
    email: email,
    phone: phone,
    location: `${city}, ${state}, ${country}`,
    investment_range: invest,
    time_horizon: horizon,
    objective: obj,
    body: decodeURIComponent(_pendingEmail) 
  };
  const btn = document.querySelector('#tab-retail .fsubmit');
  doSendEmail(btn);
}

/* â”€â”€ PROJECT FUNDING FORM â”€â”€ */
function submitProject() {
  const fname     = (document.getElementById('p-fname')?.value     || '').trim();
  const lname     = (document.getElementById('p-lname')?.value     || '').trim();
  const email     = (document.getElementById('p-email')?.value     || '').trim();
  const phoneCode = (document.getElementById('p-phone-code')?.value || '+91').trim();
  const phoneNum  = (document.getElementById('p-phone')?.value      || '').trim();
  const phoneRaw  = phoneNum ? (phoneCode + ' ' + phoneNum) : '';
  const country  = (document.getElementById('p-country')?.value   || '').trim();
  const state    = (document.getElementById('p-state')?.value     || '').trim();
  const city     = (document.getElementById('p-city')?.value      || '').trim();
  const busLoc   = (document.getElementById('p-bus-location')?.value || '').trim();
  const company  = (document.getElementById('p-company')?.value   || '').trim();
  const yourLoc  = (document.getElementById('p-your-location')?.value || '').trim();
  const invest   = (document.getElementById('p-invest')?.value    || '').trim();
  const purpose  = (document.getElementById('p-purpose')?.value   || '').trim();

  if (!fname)                                          { showError('p-error','Please enter your first name.');        return; }
  if (!lname)                                          { showError('p-error','Please enter your last name.');         return; }
  if (!email || !isValidEmail(email))                  { showError('p-error','Please enter a valid email address.');  return; }
  if (!phoneNum || !isValidPhone(phoneNum))
                                                       { showError('p-error','Please enter a valid 10-digit mobile number.'); return; }
  if (!country)                                        { showError('p-error','Please enter your country.'); return; }
  if (!state)                                          { showError('p-error','Please enter your state.'); return; }
  if (!city)                                           { showError('p-error','Please enter your city.'); return; }
  if (!busLoc)                                         { showError('p-error','Please enter your proposed business location.'); return; }
  if (!company)                                        { showError('p-error','Please enter your company name.'); return; }
  if (!yourLoc)                                        { showError('p-error','Please enter your location.'); return; }
  if (!invest)                                         { showError('p-error','Please select your investment range.'); return; }
  if (!purpose)                                        { showError('p-error','Please select your purpose.');     return; }

  const phone = normalisePhone(phoneRaw);

  _pendingWA = encodeURIComponent(
`*New WhiteFlows Lead â€” Project Funding*
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Your Location: ${yourLoc}
Company: ${company}
Business Location: ${busLoc}
Investment Range: ${invest}
Purpose: ${purpose}
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Submitted via WhiteFlows Website`);

  _pendingEmail = encodeURIComponent(
`New WhiteFlows Lead â€” Project Funding

Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Your Location: ${yourLoc}
Company: ${company}
Business Location: ${busLoc}
Investment Range: ${invest}
Purpose: ${purpose}

Submitted via WhiteFlows Website`);

  _pendingSubj     = encodeURIComponent('PROJECT FUNDING LEAD â€” ' + fname + ' ' + lname);
  _pendingFormType = 'project';
  _pendingEmailData = { 
    type: 'project', 
    form_name: 'Project Funding',
    subject: decodeURIComponent(_pendingSubj),
    name: `${fname} ${lname}`,
    email: email,
    phone: phone,
    location: `${city}, ${state}, ${country}`,
    your_location: yourLoc,
    company: company,
    business_location: busLoc,
    investment_range: invest,
    purpose: purpose,
    body: decodeURIComponent(_pendingEmail)
  };
  const btn = document.querySelector('#tab-project .fsubmit');
  doSendEmail(btn);
}

/* â”€â”€ READY TO SCALE FORM â”€â”€ */
function submitScale() {
  const fname     = (document.getElementById('s-fname')?.value     || '').trim();
  const lname     = (document.getElementById('s-lname')?.value     || '').trim();
  const email     = (document.getElementById('s-email')?.value     || '').trim();
  const phoneCode = (document.getElementById('s-phone-code')?.value || '+91').trim();
  const phoneNum  = (document.getElementById('s-phone')?.value      || '').trim();
  const phoneRaw  = phoneNum ? (phoneCode + ' ' + phoneNum) : '';
  const country  = (document.getElementById('s-country')?.value   || '').trim();
  const state    = (document.getElementById('s-state')?.value     || '').trim();
  const city     = (document.getElementById('s-city')?.value      || '').trim();
  const industry = (document.getElementById('s-industry')?.value  || '').trim();
  const estimateAmt  = (document.getElementById('s-estimate-amount')?.value || '').trim();
  const estimateUnit = (document.getElementById('s-estimate-unit')?.value  || 'Lakh').trim();
  const estimate     = estimateAmt ? (estimateAmt + ' ' + estimateUnit) : '';

  if (!fname)                                          { showError('s-error','Please enter your first name.');        return; }
  if (!lname)                                          { showError('s-error','Please enter your last name.');         return; }
  if (!email || !isValidEmail(email))                  { showError('s-error','Please enter a valid email address.');  return; }
  if (!phoneNum || !isValidPhone(phoneNum))
                                                       { showError('s-error','Please enter a valid 10-digit mobile number.'); return; }
  if (!country)                                        { showError('s-error','Please enter your country.'); return; }
  if (!state)                                          { showError('s-error','Please enter your state.'); return; }
  if (!city)                                           { showError('s-error','Please enter your city.'); return; }
  if (!industry)                                       { showError('s-error','Please enter your industry category.'); return; }
  if (!estimateAmt)                                    { showError('s-error','Please enter your estimate amount.'); return; }

  const phone = normalisePhone(phoneRaw);

  /* â”€â”€ Read proposal document (same pattern as registration form) â”€â”€ */
  const proposalInput = document.getElementById('s-proposal');
  const proposalFile  = proposalInput?.files?.[0];

  if (!proposalFile) {
    showError('s-error', 'Please upload your proposal document.');
    return;
  }

  // Validate file size (max 10 MB)
  if (proposalFile.size > 10 * 1024 * 1024) {
    showError('s-error', 'Proposal document must be under 10 MB.');
    return;
  }

  // Disable button while processing
  const scaleBtn = document.querySelector('#tab-scale .fsubmit');
  if (scaleBtn) {
    scaleBtn.classList.add('loading');
    scaleBtn.disabled = true;
  }

  // Read the file as base64 then submit
  const reader = new FileReader();
  reader.onload = function(evt) {
    const base64Data = evt.target.result; // data:type;base64,...

    _pendingWA = encodeURIComponent(
`*New WhiteFlows Lead \u2014 Ready to Scale*
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Industry: ${industry}
Estimate: ${estimate}
Proposal: ${proposalFile.name}
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
Submitted via WhiteFlows Website`);

    _pendingEmail = encodeURIComponent(
`New WhiteFlows Lead \u2014 Ready to Scale

Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Industry: ${industry}
Estimate: ${estimate}
Proposal: ${proposalFile.name}

Submitted via WhiteFlows Website`);

    _pendingSubj     = encodeURIComponent('SCALE-UP LEAD \u2014 ' + fname + ' ' + lname);
    _pendingFormType = 'scale';
    _pendingEmailData = {
      type: 'scale',
      form_name: 'Scale-Up Enquiry',
      subject: decodeURIComponent(_pendingSubj),
      name: `${fname} ${lname}`,
      email: email,
      phone: phone,
      location: `${city}, ${state}, ${country}`,
      industry: industry,
      estimate: estimate,
      body: decodeURIComponent(_pendingEmail),
      documents: {
        proposal: {
          label: 'Proposal Document',
          data: base64Data,
          type: proposalFile.type || 'application/pdf',
          originalName: proposalFile.name
        }
      }
    };
    doSendEmail(scaleBtn);

    // Re-enable button after sending
    if (scaleBtn) {
      scaleBtn.classList.remove('loading');
      scaleBtn.disabled = false;
    }
  };

  reader.onerror = function() {
    showError('s-error', 'Failed to read the proposal file. Please try again.');
    if (scaleBtn) {
      scaleBtn.disabled = false;
      scaleBtn.textContent = 'Submit for Scaling \u2192';
    }
  };

  reader.readAsDataURL(proposalFile);
}


/* â”€â”€ OCEAN FORM â”€â”€ */
function toggleOceanOther(val) {
  const group = document.getElementById('o-interest-other-group');
  if (group) group.style.display = (val === 'others') ? 'block' : 'none';
}

function submitOcean() {
  const fname     = (document.getElementById('o-fname')?.value     || '').trim();
  const lname     = (document.getElementById('o-lname')?.value     || '').trim();
  const email     = (document.getElementById('o-email')?.value     || '').trim();
  const phoneCode = (document.getElementById('o-phone-code')?.value || '+91').trim();
  const phoneNum  = (document.getElementById('o-phone')?.value      || '').trim();
  const phoneRaw  = phoneNum ? (phoneCode + ' ' + phoneNum) : '';
  const country  = (document.getElementById('o-country')?.value   || '').trim();
  const state    = (document.getElementById('o-state')?.value     || '').trim();
  const city     = (document.getElementById('o-city')?.value      || '').trim();
  const invest   = (document.getElementById('o-invest')?.value    || '').trim();
  // category field removed
  let interest   = (document.getElementById('o-interest')?.value  || '').trim();

  if (interest === 'others') {
    interest = (document.getElementById('o-interest-other')?.value || '').trim() || 'Others';
  }

  if (!fname)                                          { showError('o-error','Please enter your first name.');        return; }
  if (!lname)                                          { showError('o-error','Please enter your last name.');         return; }
  if (!email || !isValidEmail(email))                  { showError('o-error','Please enter a valid email address.');  return; }
  if (!phoneNum || !isValidPhone(phoneNum))
                                                       { showError('o-error','Please enter a valid 10-digit mobile number.'); return; }
  if (!country)                                        { showError('o-error','Please enter your country.'); return; }
  if (!state)                                          { showError('o-error','Please enter your state.'); return; }
  if (!city)                                           { showError('o-error','Please enter your city.'); return; }
  if (!invest)                                         { showError('o-error','Please select your investment range.'); return; }

  if (!interest)                                       { showError('o-error','Please select your area of interest.'); return; }

  const phone = normalisePhone(phoneRaw);

  _pendingWA = encodeURIComponent(
`*New WhiteFlows Lead â€” The Ocean Ecosystem*
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Investment Range: ${invest}
Interest: ${interest}
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Submitted via WhiteFlows Website`);

  _pendingEmail = encodeURIComponent(
`New WhiteFlows Lead â€” The Ocean Ecosystem

Name: ${fname} ${lname}
Email: ${email}
Phone: ${phone}
Location: ${city}, ${state}, ${country}
Investment Range: ${invest}
Interest: ${interest}

Submitted via WhiteFlows Website`);

  _pendingSubj     = encodeURIComponent('OCEAN ECOSYSTEM LEAD â€” ' + fname + ' ' + lname);
  _pendingFormType = 'ocean';
  _pendingEmailData = { 
    type: 'ocean', 
    form_name: 'The Ocean Ecosystem',
    subject: decodeURIComponent(_pendingSubj),
    name: `${fname} ${lname}`,
    email: email,
    phone: phone,
    location: `${city}, ${state}, ${country}`,
    investment_range: invest,
    interest: interest,
    body: decodeURIComponent(_pendingEmail)
  };
  const btn = document.querySelector('#tab-ocean .fsubmit');
  doSendEmail(btn);
}

/* â”€â”€ INSTITUTIONAL FORM â”€â”€ */
function submitInstitutional() {
  const entity    = (document.getElementById('i-entity')?.value   || '').trim();
  const email     = (document.getElementById('i-email')?.value    || '').trim();
  const contact   = (document.getElementById('i-contact')?.value  || '').trim();
  const phoneCode = (document.getElementById('i-phone-code')?.value || '+91').trim();
  const phoneNum  = (document.getElementById('i-phone')?.value      || '').trim();
  const phoneRaw  = phoneNum ? (phoneCode + ' ' + phoneNum) : '';

  if (!entity)                                         { showError('i-error','Please enter your entity name.');        return; }
  if (!email || !isValidEmail(email))                  { showError('i-error','Please enter a valid corporate email.'); return; }
  if (!contact)                                        { showError('i-error','Please enter contact person name.');     return; }
  if (!phoneNum || !isValidPhone(phoneNum))
                                                       { showError('i-error','Please enter a valid 10-digit direct number.'); return; }

  const phone      = normalisePhone(phoneRaw);
  const entityType = (document.getElementById('i-entity-type')?.value || '').trim();
  const aum        = (document.getElementById('i-aum')?.value || '').trim();

  if (!entityType) { showError('i-error','Please select your entity type.');  return; }
  if (!aum)        { showError('i-error','Please select your AUM range.');     return; }

  _pendingWA = encodeURIComponent(
`*New WhiteFlows Lead â€” Institutional/Ultra-HNI*
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Entity: ${entity}
Email: ${email}
Contact: ${contact}
Phone: ${phone}
Entity Type: ${entityType}
AUM Range: ${aum}
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Submitted via WhiteFlows Website`);

  _pendingEmail = encodeURIComponent(
`New WhiteFlows Lead â€” Institutional/Ultra-HNI

Entity: ${entity}
Email: ${email}
Contact: ${contact}
Phone: ${phone}
Entity Type: ${entityType}
AUM Range: ${aum}

Submitted via WhiteFlows Website`);

  _pendingSubj     = encodeURIComponent('INSTITUTIONAL LEAD â€” ' + entity);
  _pendingFormType = 'institutional';
  _pendingEmailData = { 
    type: 'institutional', 
    form_name: 'Institutional/Ultra-HNI',
    subject: decodeURIComponent(_pendingSubj),
    entity_name: entity,
    email: email,
    contact_person: contact,
    phone: phone,
    entity_type: entityType,
    aum_range: aum,
    body: decodeURIComponent(_pendingEmail)
  };
  const btn = document.querySelector('#tab-institutional .fsubmit');
  doSendEmail(btn);
}

// â”€â”€ Dynamic copyright year â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const yearEl = document.getElementById('copyrightYear');
if (yearEl) yearEl.textContent = new Date().getFullYear();

// â”€â”€ Scroll to top button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
(function(){
  const btn = document.getElementById('scrollTopBtn');
  if (!btn) return;
  window.addEventListener('scroll', ()=>{
    btn.classList.toggle('visible', window.scrollY > 400);
  }, { passive:true });
})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// COUNTER ANIMATION â€” Stats count up when slide 1 is active
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  let hasAnimated = false;

  function easeOutQuart(t) {
    return 1 - Math.pow(1 - t, 4);
  }

  function animateCounters() {
    if (hasAnimated) return;
    hasAnimated = true;

    const counters = document.querySelectorAll('.count-up');
    const duration = 2000; // 2 seconds total
    const startTime = performance.now();

    function step(currentTime) {
      const elapsed  = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased    = easeOutQuart(progress);

      counters.forEach(el => {
        const target = parseInt(el.dataset.target, 10);
        const suffix = el.dataset.suffix || '';
        const current = Math.floor(eased * target);
        el.textContent = current;
        // append suffix as styled span once at end
        if (progress >= 1) {
          el.innerHTML = target + '<span class="stat-suffix">' + suffix + '</span>';
        }
      });

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    }

    requestAnimationFrame(step);
  }

  // Trigger when slide 1 becomes active (carousel shows it)
  // Use IntersectionObserver on heroStats
  const statsEl = document.getElementById('heroStats');
  if (!statsEl) return;

  // Also hook into carousel â€” re-trigger on return to slide 1
  const origGoTo = window.carouselGoTo;
  const origMove = window.carouselMove;

  function checkAndAnimate(targetIdx) {
    if (targetIdx === 0) {
      hasAnimated = false; // reset so it re-animates
      setTimeout(animateCounters, 400); // wait for slide transition
    }
  }

  window.carouselGoTo = function(idx) {
    if (origGoTo) origGoTo(idx);
    checkAndAnimate(idx);
  };
  window.carouselMove = function(dir) {
    if (origMove) origMove(dir);
  };

  // Trigger on first page load â€” slide 1 is default
  // Wait for page to fully render
  if (document.readyState === 'complete') {
    setTimeout(animateCounters, 600);
  } else {
    window.addEventListener('load', () => setTimeout(animateCounters, 600));
  }
})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// TESTIMONIALS CAROUSEL
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  const track    = document.getElementById('testiTrack');
  const dotsWrap = document.getElementById('testiNav');
  if (!track || !dotsWrap) return;

  const cards     = track.querySelectorAll('.testi-card');
  const dots      = dotsWrap.querySelectorAll('.testi-dot');
  const total     = cards.length;           // 5 cards
  const visible   = getVisible();           // 3 on desktop, 2 on tablet, 1 mobile
  const maxIndex  = total - visible;        // max slide position
  let   current   = 0;
  let   autoTimer = null;
  let   startX    = 0;

  function getVisible() {
    if (window.innerWidth <= 640)  return 1;
    if (window.innerWidth <= 1024) return 2;
    return 3;
  }

  function getCardWidth() {
    if (!cards[0]) return 0;
    const gap    = 28;
    const wrap   = track.parentElement.clientWidth;
    const vis    = getVisible();
    return (wrap - gap * (vis - 1)) / vis;
  }

  function goTo(idx) {
    current = Math.max(0, Math.min(idx, maxIndex));
    const cardW = getCardWidth();
    const gap   = 28;
    track.style.transform = `translateX(-${current * (cardW + gap)}px)`;

    // Update dots â€” 3 dots represent start, middle, end
    const dotIdx = current === 0 ? 0 : current >= maxIndex ? 2 : 1;
    dots.forEach((d, i) => d.classList.toggle('active', i === dotIdx));
  }

  function next() { goTo(current + 1 > maxIndex ? 0 : current + 1); }
  function prev() { goTo(current - 1 < 0 ? maxIndex : current - 1); }

  function startAuto() {
    clearInterval(autoTimer);
    autoTimer = setInterval(next, 4000);
  }
  function stopAuto()  { clearInterval(autoTimer); }

  // Dot clicks
  dots.forEach((dot, i) => {
    dot.addEventListener('click', () => {
      stopAuto();
      // map 3 dots to positions: 0, middle, maxIndex
      const positions = [0, Math.floor(maxIndex / 2), maxIndex];
      goTo(positions[i] || 0);
      startAuto();
    });
  });

  // Touch swipe
  track.addEventListener('touchstart', e => { startX = e.touches[0].clientX; stopAuto(); }, { passive:true });
  track.addEventListener('touchend',   e => {
    const diff = startX - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 40) diff > 0 ? next() : prev();
    startAuto();
  }, { passive:true });

  // Pause on hover
  track.addEventListener('mouseenter', stopAuto);
  track.addEventListener('mouseleave', startAuto);

  // Recalculate on resize
  window.addEventListener('resize', () => goTo(0), { passive:true });

  // Boot
  goTo(0);
  startAuto();
})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// FIX 5 â€” PAGE ENTRANCE ANIMATION
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  // Trigger entrance elements right after DOM loads
  function triggerEntrance() {
    document.querySelectorAll('.page-entrance').forEach((el, i) => {
      setTimeout(() => el.classList.add('entered'), 80 + i * 100);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', triggerEntrance);
  } else {
    triggerEntrance();
  }
})();

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// FIX 6 â€” PHILOSOPHY PILLAR STAGGERED ENTRANCE
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  const pillars = document.querySelectorAll('.pillar-animate');
  if (!pillars.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

  pillars.forEach(p => observer.observe(p));
})();

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// FIX 7 â€” COOKIE CONSENT BANNER
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  const bar     = document.getElementById('cookieBar');
  const accept  = document.getElementById('cookieAccept');
  const decline = document.getElementById('cookieDecline');
  if (!bar) return;

  const COOKIE_KEY = 'wf_cookie_consent';

  function hideCookieBar() {
    bar.classList.remove('visible');
    // After transition completes, remove from layout
    setTimeout(() => { bar.style.display = 'none'; }, 450);
  }

  // Only show if user hasn't already decided
  if (!localStorage.getItem(COOKIE_KEY)) {
    // Slide up after 1.5 seconds
    setTimeout(() => bar.classList.add('visible'), 1500);
  }

  accept?.addEventListener('click', () => {
    localStorage.setItem(COOKIE_KEY, 'accepted');
    hideCookieBar();
  });

  decline?.addEventListener('click', () => {
    localStorage.setItem(COOKIE_KEY, 'declined');
    hideCookieBar();
  });
})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// FIX 3 â€” FORM ABANDONMENT PROTECTION (beforeunload)
// Uses a clean boolean flag â€” cleared when user submits
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  // Global flag â€” set true the moment user clicks send
  window._wfSubmitting = false;

  const WATCHED_IDS = ['r-fname','r-lname','r-email','r-phone',
                       'p-fname','p-lname','p-email','p-phone',
                       's-fname','s-lname','s-email','s-phone',
                       'o-fname','o-lname','o-email','o-phone',
                       'i-entity','i-email','i-contact','i-phone'];

  function formHasData() {
    return WATCHED_IDS.some(id => {
      const el = document.getElementById(id);
      if (!el) return false;
      const val = el.value.trim();
      return val && val !== '+91' && val !== '+91 ';
    });
  }

  window.addEventListener('beforeunload', function(e) {
    // Do NOT warn if user intentionally submitted
    if (window._wfSubmitting) return;
    if (formHasData()) {
      e.preventDefault();
      e.returnValue = '';
    }
  });
})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// ACTIVE NAV LINK ON SCROLL â€” IntersectionObserver
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  const navLinks = document.querySelectorAll('.nav-links a[data-section]');
  if (!navLinks.length) return;

  // Map section-id â†’ nav link
  const linkMap = {};
  navLinks.forEach(link => {
    const sec = link.dataset.section;
    if (sec) linkMap[sec] = link;
  });

  // Also add #contact â†’ footer
  const footer = document.querySelector('footer');
  if (footer && !footer.id) footer.id = 'contact';

  let activeSection = null;

  function setActive(id) {
    if (activeSection === id) return;
    activeSection = id;
    navLinks.forEach(l => l.classList.remove('nav-active'));
    if (id && linkMap[id]) {
      linkMap[id].classList.add('nav-active');
    }
  }

  // Use IntersectionObserver on each section
  const sections = document.querySelectorAll('section[id]');
  
  const observer = new IntersectionObserver((entries) => {
    // Find the entry with highest intersection ratio that is intersecting
    let best = null;
    let bestRatio = 0;
    
    entries.forEach(entry => {
      if (entry.isIntersecting && entry.intersectionRatio > bestRatio) {
        bestRatio = entry.intersectionRatio;
        best = entry.target.id;
      }
    });
    
    if (best) setActive(best);
  }, {
    threshold: [0.15, 0.3, 0.5],
    rootMargin: '-80px 0px -40% 0px'
  });

  sections.forEach(sec => observer.observe(sec));

  // Also handle scroll to top â€” clear active
  window.addEventListener('scroll', () => {
    if (window.scrollY < 100) setActive(null);
  }, { passive: true });

})();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// REFERENCE MARKET DATA â€” Illustrative snapshot for presentation
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  // Reference prices used for the on-page illustrative snapshot
  const STOCKS = [
    { id:'sensex',    ticker:'SENSEX',     label:'Sensex',    name:'BSE:SENSEX',    price:73456.80, isIndex:true  },
    { id:'nifty',     ticker:'NIFTY 50',   label:'Nifty 50',  name:'NSE:NIFTY',     price:22189.40, isIndex:true  },
    { id:'banknifty', ticker:'BANK NIFTY', label:'Bank Nifty',name:'NSE:BANKNIFTY', price:46820.15, isIndex:true  },
    { id:'reliance',  ticker:'RELIANCE',   label:'Reliance',  name:'BSE:RELIANCE',  price:2845.60,  isIndex:false },
    { id:'tcs',       ticker:'TCS',        label:'TCS',       name:'BSE:TCS',       price:3920.75,  isIndex:false },
    { id:'hdfc',      ticker:'HDFC BANK',  label:'HDFC Bank', name:'BSE:HDFCBANK',  price:1542.30,  isIndex:false },
    { id:'infy',      ticker:'INFOSYS',    label:'Infosys',   name:'BSE:INFY',      price:1678.45,  isIndex:false },
    { id:'icici',     ticker:'ICICI BANK', label:'ICICI Bank',name:'BSE:ICICIBANK', price:1089.70,  isIndex:false },
    { id:'sbi',       ticker:'SBI',        label:'SBI',       name:'BSE:SBI',       price:762.40,   isIndex:false },
  ];
  const COMMS = [
    { id:'gold',   name:'Gold / 10g',  price:62840,  currency:'â‚¹', decimals:0 },
    { id:'silver', name:'Silver / kg', price:74210,  currency:'â‚¹', decimals:0 },
    { id:'usd',    name:'USD / INR',   price:83.42,  currency:'â‚¹', decimals:2 },
    { id:'crude',  name:'Crude / bbl', price:78.40,  currency:'$', decimals:2 },
  ];
  // Track running prices and open prices
  const prices = {};
  const opens = {};
  STOCKS.forEach(s => { prices[s.id] = s.price; opens[s.id] = s.price; });
  COMMS.forEach(c => { prices[c.id] = c.price; opens[c.id] = c.price; });

  // Random drift helper
  function drift(current, maxPct) {
    const change = (Math.random() - 0.48) * 2 * maxPct;
    return current * (1 + change / 100);
  }

  function fmt(v, decimals) {
    return v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }

  function updateTime() {
    const el = document.getElementById('tickerTime');
    const su = document.getElementById('snapUpdated');
    if (el) el.textContent = 'Illustrative View';
    if (su) su.textContent = 'Reference data';
  }

  function updateTicker() {
    const track = document.getElementById('tickerTrack');
    if (!track) return;
    const items = STOCKS.map(s => {
      const p = prices[s.id];
      const ch = p - opens[s.id];
      const pct = (ch / opens[s.id]) * 100;
      const cls = pct >= 0 ? 'up' : 'down';
      const arrow = pct >= 0 ? '&#9650;' : '&#9660;';
      const dec = s.isIndex ? 2 : 2;
      return `<div class="ticker-item">
        <span class="ticker-symbol">${s.ticker}</span>
        <span class="ticker-price">&#8377;${fmt(p, dec)}</span>
        <span class="ticker-change ${cls}">${arrow} ${Math.abs(pct).toFixed(2)}%</span>
      </div>`;
    });
    track.innerHTML = items.join('') + items.join('');
  }

  function updateSnapshot() {
    const snap = document.getElementById('marketSnapshot');
    if (!snap) return;
    const header = `<div class="snap-row snap-header"><span>Symbol</span><span>Price</span><span>Change</span><span>%</span></div>`;
    const rows = STOCKS.map(s => {
      const p = prices[s.id];
      const ch = p - opens[s.id];
      const pct = (ch / opens[s.id]) * 100;
      const cls = pct >= 0 ? 'up' : 'down';
      const sign = ch >= 0 ? '+' : '';
      const dec = s.isIndex ? 2 : 2;
      return `<div class="snap-row">
        <div><div class="snap-symbol">${s.label}</div><div class="snap-name">${s.name}</div></div>
        <div class="snap-price">&#8377;${fmt(p, dec)}</div>
        <div class="snap-ch ${cls}">${sign}${fmt(ch, dec)}</div>
        <div class="snap-pct ${cls}">${sign}${pct.toFixed(2)}%</div>
      </div>`;
    });
    snap.innerHTML = header + rows.join('');
  }

  function updateCommodities() {
    const commCards = document.querySelectorAll('.comm-card');
    COMMS.forEach((c, i) => {
      const card = commCards[i];
      if (!card) return;
      const p = prices[c.id];
      const ch = p - opens[c.id];
      const pct = (ch / opens[c.id]) * 100;
      const cls = pct >= 0 ? 'up' : 'down';
      const sign = pct >= 0 ? '+' : '';
      const arrow = pct >= 0 ? '&#8593;' : '&#8595;';
      const priceEl = card.querySelector('.comm-price');
      const changeEl = card.querySelector('.comm-change');
      if (priceEl) priceEl.textContent = c.currency + fmt(p, c.decimals);
      if (changeEl) {
        changeEl.className = 'comm-change ' + cls;
        changeEl.style.color = pct >= 0 ? '#16a34a' : '#dc2626';
        changeEl.innerHTML = `${sign}${pct.toFixed(2)}% ${arrow}`;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function() {
    updateTime();
  });
})();

/* â•â• PORTFOLIO MODAL DATA â•â• */
const portfolioData = {
  samyak: {
    badge: 'Flagship Â· Bestseller',
    title: 'Samyak',
    tagline: 'Balanced Growth & Long-Term Stability',
    irr: '18â€“22%',
    min: 'â‚¹5,00,000',
    rebalance: 'Quarterly',
    horizon: '3â€“5 Years',
    strategy: 'Samyak Portfolios (Right Earnings) : Investing in Harmony with Nature\n\nFor those who walk the path of the Ashtaang Maarg and value ethical living, we present Samyak Portfolios. Rooted in the sacred principles of Ahimsa (non-violence) and Satya (truth), these portfolios are designed for investors who believe that wealth should be earned with a clear conscience.\n\nOur rigorous screening process ensures your capital stays away from industries involving weapons, meat processing, intoxicants, and environmental harm. Instead, we channel your investments into businesses that are socially responsible, ecologically sustainable, and ethically governed. Grow your prosperity while staying true to your spiritual foundations.',
    holdings: ['FMCG Leaders','Banking & NBFC','IT & Technology','Infrastructure','Healthcare','Consumer Durables','Auto & Ancillaries','Capital Goods'],
    riskWidth: '40%',
    riskColor: 'linear-gradient(90deg, #4CAF50, #8BC34A)',
    bestFor: '<strong>Long-term wealth builders</strong> seeking disciplined compounding with ethical discipline. Ideal for first-time advisory clients, salaried professionals, and families building inter-generational wealth.',
    cta: 'Register Now'
  },
  halaal: {
    badge: 'Shariah-Certified',
    title: 'â˜ª Halaal Portfolio',
    tagline: 'Principled Investing â€” 100% Shariah Compliant',
    irr: '15â€“20%',
    min: 'â‚¹3,00,000',
    rebalance: 'Quarterly',
    horizon: '3â€“7 Years',
    strategy: 'Halaal Portfolios : Your Wealth, Purified.\n\nExperience an investment strategy where ethics meet performance. Our Halaal Portfolio undergoes rigorous Shariah screening to ensure every instrument is free from interest-bearing assets, tobacco, alcohol, gambling, and conventional finance.\n\nLeveraging the 37-years legacy of Indiaâ€™s oldest brokerage houses and modern execution of WhiteFlows, we provide a verified, ethical gateway to the markets. Invest with clarity, knowing your growth is built on a foundation of integrity.',
    holdings: ['IT & Software','Halaal-screened FMCG','Healthcare & Pharma','Real Estate (REIT)','Renewables & Clean Energy','Consumer Goods','Export-Oriented Equities'],
    riskWidth: '35%',
    riskColor: 'linear-gradient(90deg, #27ae60, #2ecc71)',
    bestFor: '<strong>Muslim investors</strong> who refuse to compromise faith for returns, and <strong>ESG-conscious investors</strong> seeking ethical, impact-driven wealth creation. The only fully Halaal-verified advisory in Gujarat.',
    cta: 'Register Now'
  },
  fno: {
    badge: 'Advanced Â· HNI Only',
    title: 'F&O Strategies',
    tagline: 'Algorithmic Derivatives & Options',
    irr: '25â€“35%',
    min: 'â‚¹10,00,000',
    rebalance: 'Weekly',
    horizon: '1â€“2 Years',
    strategy: 'Professional-grade options strategies engineered for consistent premium collection and downside protection. We deploy covered calls, iron condors, and directional futures with strict risk overlays â€” no naked exposure. Every strategy is algo-assisted and manually reviewed by our senior derivatives desk. Designed for investors who understand leverage and want institutional-quality execution.',
    holdings: ['Nifty 50 Options','Bank Nifty Options','Stock Futures (Top 50)','Hedged Index Spreads','Volatility Arbitrage','Momentum Derivatives'],
    riskWidth: '72%',
    riskColor: 'linear-gradient(90deg, #f39c12, #e74c3c)',
    bestFor: '<strong>HNI & Ultra-HNI investors</strong> with existing market exposure seeking high-frequency alpha. Requires minimum 1 year of market experience. <strong>Not suitable for first-time investors.</strong>',
    cta: 'Register Now'
  },
  thematic: {
    badge: 'Thematic Â· Forward-Looking',
    title: 'Thematic Portfolio',
    tagline: "India's Next Decade â€” Concentrated Sector Bets",
    irr: '20â€“30%',
    min: 'â‚¹5,00,000',
    rebalance: 'Monthly',
    horizon: '2â€“5 Years',
    strategy: "We bet on India's structural transformation. This portfolio takes concentrated, high-conviction positions in themes that will define the next decade â€” Electric Vehicles, Artificial Intelligence, Green Energy, Defence self-reliance, and Digital Infrastructure. Each theme is backed by policy tailwind, demographic shift, and capital cycle. We ride the wave before the crowd arrives.",
    holdings: ['EV & Auto Transition','AI & Data Centers','Solar & Wind Energy','Defence PSUs','Digital Infrastructure','Semiconductors','Space & Deep Tech','Agri-Tech'],
    riskWidth: '60%',
    riskColor: 'linear-gradient(90deg, #8e44ad, #e74c3c)',
    bestFor: '<strong>Forward-thinking investors</strong> who want to own India\'s future. Best for those with a 3â€“5 year horizon who can absorb short-term volatility for high long-term upside. Ideal as a satellite allocation (20â€“30% of total portfolio).',
    cta: 'Register Now'
  },
  aggressive: {
    badge: 'High Risk Â· High Reward',
    title: 'Aggressive Portfolio',
    tagline: 'Maximum Capital Growth â€” No Compromises',
    irr: '30â€“40%',
    min: 'â‚¹3,00,000',
    rebalance: 'Active',
    horizon: '5+ Years',
    strategy: 'Built for investors who understand that true wealth is built in small and micro-caps before the institutions arrive. We hunt turnaround stories, hidden compounders, and momentum plays with asymmetric upside. Active monitoring every day. No passive holding â€” if a thesis breaks, we exit. Maximum growth, maximum discipline. Not for the faint-hearted.',
    holdings: ['Small-cap Compounders','Micro-cap Turnarounds','Momentum Breakouts','Operator-driven Stocks','IPO Plays','Commodity Cyclicals','Midcap Special Sits'],
    riskWidth: '88%',
    riskColor: 'linear-gradient(90deg, #e74c3c, #c0392b)',
    bestFor: '<strong>Young, growth-oriented investors</strong> with a 5+ year horizon and the emotional discipline to hold through volatility. Maximum 20â€“25% of total portfolio allocation recommended. <strong>Capital loss risk is real â€” invest only what you can afford to grow aggressively.</strong>',
    cta: 'Register Now'
  },
  conservative: {
    badge: 'Capital Safe Â· Steady',
    title: 'Conservative Portfolio',
    tagline: 'Preserve First, Grow Second',
    irr: '10â€“14%',
    min: 'â‚¹2,00,000',
    rebalance: 'Semi-Annual',
    horizon: '2â€“4 Years',
    strategy: 'Safety without sacrificing growth. This portfolio combines India\'s finest bluechip equities with high-quality bonds and dividend-generating instruments. We prioritise capital preservation above all â€” every holding must pass a strict downside-protection filter. Designed to sleep soundly at night while your wealth grows quietly and consistently.',
    holdings: ['Nifty 50 Bluechips','Government Bonds (G-Sec)','AAA Corporate Bonds','High-Dividend PSUs','Debt Mutual Funds','Gold ETF (Hedge)','Defensive FMCG'],
    riskWidth: '20%',
    riskColor: 'linear-gradient(90deg, #2ecc71, #27ae60)',
    bestFor: '<strong>Retirees, senior citizens</strong>, and conservative investors who need predictable, stable income without sleepless nights. Also ideal as the <strong>core holding (60â€“70%)</strong> in a diversified portfolio for any age group.',
    cta: 'Register Now'
  }
};

function openPortfolioModal(key) {
  const d = portfolioData[key];
  if (!d) return;

  document.getElementById('pfModalBadge').textContent    = d.badge;
  document.getElementById('pfModalTitle').textContent    = d.title;
  document.getElementById('pfModalTagline').textContent  = d.tagline;
  document.getElementById('pfStatIRR').textContent       = d.irr;
  document.getElementById('pfStatMin').textContent       = d.min;
  document.getElementById('pfStatRebalance').textContent = d.rebalance;
  document.getElementById('pfStatHorizon').textContent   = d.horizon;
  document.getElementById('pfModalStrategy').textContent = d.strategy;
  document.getElementById('pfModalBestFor').innerHTML    = d.bestFor;
  document.getElementById('pfModalCTAText').textContent  = d.cta;

  const holdingsEl = document.getElementById('pfModalHoldings');
  holdingsEl.innerHTML = d.holdings.map(h => `<span class="pf-modal-holding-tag">${h}</span>`).join('');

  const fill = document.getElementById('pfModalRiskFill');
  fill.style.background = d.riskColor;
  fill.style.width = '0%';
  setTimeout(() => { fill.style.width = d.riskWidth; }, 80);

  document.getElementById('pfModalOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.getElementById('pfModal').scrollTop = 0;
}

function closePortfolioModal() {
  document.getElementById('pfModalOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

function closePfModalOnBg(e) {
  if (e.target === document.getElementById('pfModalOverlay')) closePortfolioModal();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closePortfolioModal(); });

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// ILLUSTRATIVE NEWS PANEL â€” WhiteFlows reference commentary
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
(function(){
  const NEWS_POOL = [
    { source:'WhiteFlows Desk', sentiment:'sent-neutral', label:'Theme', headline:'Macro positioning should be reviewed alongside rates, liquidity, and earnings breadth.', age:1 },
    { source:'WhiteFlows Desk', sentiment:'sent-positive', label:'Focus', headline:'Large-cap quality and cash-flow durability typically matter more than market noise across full cycles.', age:2 },
    { source:'WhiteFlows Desk', sentiment:'sent-neutral', label:'Commodities', headline:'Gold, silver, currency, and crude remain useful reference assets when reading broader risk sentiment.', age:3 },
    { source:'WhiteFlows Desk', sentiment:'sent-positive', label:'Funding', headline:'Capital structuring conversations should always be matched to mandate, runway, and promoter alignment.', age:4 },
    { source:'WhiteFlows Desk', sentiment:'sent-negative', label:'Risk', headline:'Suitability, downside tolerance, and time horizon should lead portfolio construction before return targets.', age:5 },
    { source:'WhiteFlows Desk', sentiment:'sent-neutral', label:'Discipline', headline:'Compounding is usually protected by disciplined position sizing, not by reacting to every short-term move.', age:6 },
  ];

  function buildAge(h) {
    return 'Illustrative commentary';
  }

  function renderNews() {
    const list = document.getElementById('newsList');
    if (!list) return;
    list.innerHTML = NEWS_POOL.map(n => `
      <a class="news-card" href="#register" onclick="switchTab('retail')">
        <div class="news-card-source">${n.source} <span class="news-card-sentiment ${n.sentiment}">${n.label}</span></div>
        <div class="news-card-headline">${n.headline}</div>
        <div class="news-card-meta">${buildAge(n.age)} | Consultation-led analysis</div>
      </a>`).join('');
  }

  document.addEventListener('DOMContentLoaded', function() {
    renderNews();
  });
})();

let _currentPortfolioLabel = 'Portfolio';

  const _uploadedFiles = {};

  function handleUpload(input, cardId, statusId, prevId) {
    const file = input.files && input.files[0];
    const card = document.getElementById(cardId);
    const status = document.getElementById(statusId);
    const prev = document.getElementById(prevId);
    
    if (!file) return;

    // ELITE VALIDATION: 3MB Limit (Absolute Safety for Gmail's 25MB encoded limit)
    const MAX_SIZE = 3 * 1024 * 1024; 
    if (file.size > MAX_SIZE) {
      showToast('Institutional Security Alert: File exceeds 3MB limit.');
      input.value = ''; 
      card.classList.remove('vault-verifying');
      return;
    }

    // Start "Verifying" State
    card.classList.add('vault-verifying');
    status.innerHTML = '<span class="vault-spinner"></span> Securely Scanning...';

    const docKey = input.name;
    const reader = new FileReader();

    reader.onload = function(e) {
      // Small artificial delay to show the "Elite" scanning process
      setTimeout(() => {
        _uploadedFiles[docKey] = { name: file.name, type: file.type, data: e.target.result };
        
        // Success State
        card.classList.remove('vault-verifying');
        card.classList.add('uploaded');
        
        status.innerHTML = '<span class="vault-secure-tick">[âœ”]</span> ' + file.name.substring(0, 15) + (file.name.length > 15 ? '...' : '') + ' <small style="opacity:0.6; font-size:9px;">SECURE</small>';
        
        if (file.type.startsWith('image/')) {
          prev.src = e.target.result;
        } else {
          prev.src = ''; // PDF placeholder could go here
        }

        if (typeof updateRegProgress === 'function') updateRegProgress();

        // Add remove btn if not present
        if (!card.querySelector('.reg-upload-remove')) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'reg-upload-remove';
          btn.innerHTML = '&times;';
          btn.onclick = function(ev) {
            ev.stopPropagation();
            input.value = '';
            delete _uploadedFiles[docKey];
            card.classList.remove('uploaded');
            prev.src = '';
            status.textContent = 'Tap to upload';
            btn.remove();
            if (typeof updateRegProgress === 'function') updateRegProgress();
          };
          card.appendChild(btn);
        }
      }, 800);
    };
    
    reader.onerror = function() {
      card.classList.remove('vault-verifying');
      showError('reg-error', 'System Error: Could not verify document. Please try again.');
    };

    reader.readAsDataURL(file);
  }

  function fileSelected(input, zoneId, nameId) {
    // legacy stub kept for compatibility
  }

  var currentRegStep = 1;

  function saveRegState() {
    const data = {
      step: currentRegStep,
      fields: {}
    };
    const form = document.getElementById('regForm');
    if (!form) return;
    form.querySelectorAll('input:not([type="file"]), select').forEach(el => {
      if (el.id) data.fields[el.id] = el.value;
    });
    sessionStorage.setItem('wf_reg_state', JSON.stringify(data));
  }

  function loadRegState() {
    const raw = sessionStorage.getItem('wf_reg_state');
    if (!raw) return false;
    try {
      const data = JSON.parse(raw);
      for (let id in data.fields) {
        const el = document.getElementById(id);
        if (el) el.value = data.fields[id];
      }
      currentRegStep = data.step || 1;
      changeRegStep(0);
      if (typeof updateRegProgress === 'function') updateRegProgress();
      return true;
    } catch(e) { return false; }
  }

  function clearRegState() {
    sessionStorage.removeItem('wf_reg_state');
  }

  function changeRegStep(delta) {
    if (delta > 0) {
      if (!checkStepValidity(currentRegStep)) {
        if (typeof showToast === 'function') showToast('Please fill in all required fields to proceed.');
        else alert('Please fill in all required fields.');
        return;
      }
    }

    currentRegStep += delta;
    if (currentRegStep < 1) currentRegStep = 1;
    if (currentRegStep > 3) currentRegStep = 3;
    
    saveRegState();

    var inner = document.getElementById('regStepsInner');
    if (inner) {
      inner.style.transform = 'translateX(-' + ((currentRegStep - 1) * 33.333) + '%)';
    }

    // Toggle Buttons
    document.getElementById('regBtnBack').classList.toggle('reg-hide', currentRegStep === 1);
    document.getElementById('regBtnNext').classList.toggle('reg-hide', currentRegStep === 3);
    document.getElementById('regSubmitBtn').classList.toggle('reg-hide', currentRegStep !== 3);

    // Update step indicator dots
    [1,2,3].forEach(function(i) {
      var dot = document.getElementById('rstep' + i);
      if (dot) {
        dot.classList.toggle('active', i === currentRegStep);
        dot.classList.toggle('done', i < currentRegStep);
      }
      var lbl = document.getElementById('rlabel' + i);
      if (lbl) lbl.classList.toggle('active', i === currentRegStep);
    });
    [1,2].forEach(function(i) {
      var line = document.getElementById('rline' + i);
      if (line) line.classList.toggle('active', i < currentRegStep);
    });

    // Scroll to top of modal
    var modal = document.getElementById('regModal');
    if (modal) modal.scrollTop = 0;
  }

  function checkStepValidity(step) {
    var stepEl = document.querySelectorAll('.reg-step')[step - 1];
    if (!stepEl) return true;
    var inputs = stepEl.querySelectorAll('input[required], select[required]');
    var isValid = true;
    inputs.forEach(function(input) {
      if (input.type === 'file') {
        // Handled during final submit
      } else {
        var val = input.value.trim();
        var fieldValid = !!val;
        var msg = '';

        if (!val) {
          fieldValid = false;
        } else if (input.type === 'email' && !isValidEmail(val)) {
          fieldValid = false;
          msg = 'Invalid email';
        } else if (input.type === 'tel' && !isValidPhone(val)) {
          fieldValid = false;
          msg = 'Must be 10 digits';
        } else if (input.id === 'regNomineePAN' && !isValidPAN(val)) {
          fieldValid = false;
          msg = 'Invalid PAN format';
        } else if (input.id === 'regNomineeDOB') {
          var d = new Date(val);
          if (d >= new Date()) {
            fieldValid = false;
            msg = 'DOB must be in the past';
          }
        }

        if (!fieldValid) {
          isValid = false;
          input.style.borderColor = '#FF4D4D';
          if (msg && typeof showToast === 'function') showToast(msg);
          setTimeout(function() { input.style.borderColor = ''; }, 3000);
        }
      }
    });
    return isValid;
  }

  function openRegModal(customLabel, forceReset) {
    const tagEl = document.getElementById('regPortfolioTag');
    if (tagEl) {
      if (customLabel) {
        tagEl.textContent = customLabel;
      } else {
        const titleEl = document.getElementById('pfModalTitle');
        tagEl.textContent = titleEl ? titleEl.textContent.trim() + ' Portfolio' : 'General Registration';
      }
    }
    ['regForm','regSending','regSuccess','regReadyPanel'].forEach(function(id) {
      const el = document.getElementById(id);
      if (el) { el.style.display = 'none'; el.style.flexDirection = ''; }
    });
    const form = document.getElementById('regForm');
    if (form) {
      form.style.display = '';
      if (forceReset) {
        form.reset();
        clearRegState();
        currentRegStep = 1;
        changeRegStep(0);
        Object.keys(_uploadedFiles).forEach(function(k) { delete _uploadedFiles[k]; });
        document.querySelectorAll('.reg-upload-card').forEach(function(card) {
          card.classList.remove('uploaded');
          var rem = card.querySelector('.reg-upload-remove');
          if (rem) rem.remove();
          var prev = card.querySelector('.reg-upload-preview');
          if (prev) prev.src = '';
        });
        document.querySelectorAll('.reg-upload-status').forEach(function(s) { s.textContent = 'Tap to upload'; });
      } else {
        if (!loadRegState()) {
          currentRegStep = 1;
          changeRegStep(0);
        }
      }
    }
    closePortfolioModal();
    const overlay = document.getElementById('regOverlay');
    if (overlay) {
      overlay.classList.add('reg-open');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeRegModal() {
    const overlay = document.getElementById('regOverlay');
    if (overlay) {
      overlay.classList.remove('reg-open');
      document.body.style.overflow = '';
    }
  }

  function closeRegOnBg(e) {
    if (e.target === document.getElementById('regOverlay')) closeRegModal();
  }

  function _showSuccess(name) {
    // Update name in success message
    const nameEl = document.getElementById('regSuccessName');
    if (nameEl) nameEl.textContent = name;
    
    // Hide form, show success panel
    const form = document.getElementById('regForm');
    const succ = document.getElementById('regSuccess');
    if (form) form.style.display = 'none';
    if (succ) {
      succ.classList.remove('reg-hide');
      succ.style.display = 'flex';
      succ.style.flexDirection = 'column';
    }

    if (typeof showToast === 'function') showToast('Application submitted! Our advisor will contact you within 24 hours.');
    
    // Auto-close and reset after a delay
    setTimeout(function() { 
      closeRegModal(); 
      // Reset for next time
      setTimeout(() => {
        if (form) {
          form.reset();
          clearRegState();
          currentRegStep = 1;
          changeRegStep(0);
          Object.keys(_uploadedFiles).forEach(function(k) { delete _uploadedFiles[k]; });
          document.querySelectorAll('.reg-upload-card').forEach(function(card) {
            card.classList.remove('uploaded');
            var rem = card.querySelector('.reg-upload-remove');
            if (rem) rem.remove();
            var prev = card.querySelector('.reg-upload-preview');
            if (prev) prev.src = '';
          });
          document.querySelectorAll('.reg-upload-status').forEach(function(s) { s.textContent = 'Tap to upload'; });
        }
        if (succ) {
          succ.classList.add('reg-hide');
          succ.style.display = 'none';
        }
      }, 500);
    }, 4000);
  }

  function _setBtnState(loading) {
    var btn = document.getElementById('regSubmitBtn') || document.querySelector('.reg-btn-submit');
    if (!btn) return;
    btn.disabled = loading;
    if (loading) btn.classList.add('loading'); else btn.classList.remove('loading');
  }

  function updateRegProgress() {
    var fields = [
      'regApplicantName', 'regEmail', 'regMobile',
      'regNomineeName', 'regNomineePAN', 'regNomineeDOB', 'regNomineeMobile'
    ];
    var filled = 0;
    fields.forEach(function(id) {
      if (document.getElementById(id)?.value.trim()) filled++;
    });
    // Check uploads (5 docs)
    if (window._uploadedFiles) {
      if (_uploadedFiles.doc_aadhar)  filled++;
      if (_uploadedFiles.doc_pan)     filled++;
      if (_uploadedFiles.doc_cheque)  filled++;
      if (_uploadedFiles.doc_sign)    filled++;
      if (_uploadedFiles.doc_selfie)  filled++;
    }
    var total = fields.length + 5; // 7 text + 5 file
    var pct = Math.round((filled / total) * 100);
    var bar = document.getElementById('regProgressBar');
    if (bar) bar.style.width = pct + '%';
    
    saveRegState();
  }

  // Attach listeners to reg form
  document.addEventListener('DOMContentLoaded', function() {
    var rf = document.getElementById('regForm');
    if (rf) {
      rf.querySelectorAll('input, select').forEach(function(inp) {
        inp.addEventListener('input', updateRegProgress);
        inp.addEventListener('change', updateRegProgress);
      });
    }
  });

  function submitRegForm(e) {
    if (e) e.preventDefault();

    var name      = document.getElementById('regApplicantName').value.trim();
    var email     = document.getElementById('regEmail').value.trim();
    var mCode     = (document.getElementById('regMobile-code')?.value || '+91').trim();
    var mNum      = (document.getElementById('regMobile')?.value || '').trim();
    var mobile    = mNum ? (mCode + ' ' + mNum) : '';
    
    var nomName   = document.getElementById('regNomineeName').value.trim();
    var nomPAN    = document.getElementById('regNomineePAN').value.trim();
    var nomDOB    = document.getElementById('regNomineeDOB').value;
    var nCode     = (document.getElementById('regNomineeMobile-code')?.value || '+91').trim();
    var nNum      = (document.getElementById('regNomineeMobile')?.value || '').trim();
    var nomMob    = nNum ? (nCode + ' ' + nNum) : '';
    var portfolio = _currentPortfolioLabel;

    if (!name || !email || !mNum || !nomName || !nomPAN || !nomDOB || !nNum) {
      showToast('Please fill in all required fields.');
      return;
    }
    if (!isValidEmail(email)) {
      showToast('Please enter a valid applicant email.');
      return;
    }
    if (!isValidPhone(mNum)) {
      showToast('Applicant mobile must be 10 digits.');
      return;
    }
    if (!isValidPAN(nomPAN)) {
      showToast('Please enter a valid 10-character Nominee PAN.');
      return;
    }
    if (!isValidPhone(nNum)) {
      showToast('Nominee mobile must be 10 digits.');
      return;
    }

    // âœ… P0: Enforce ALL 5 file uploads are mandatory
    var requiredDocs = ['doc_aadhar', 'doc_pan', 'doc_cheque', 'doc_sign', 'doc_selfie'];
    var missingDocs = [];
    
    requiredDocs.forEach(function(docKey) {
      if (!_uploadedFiles || !_uploadedFiles[docKey]) {
        missingDocs.push(docKey);
        
        // Add red border to missing upload card
        var card = document.getElementById('ucard_' + docKey.replace('doc_', ''));
        if (card) {
          card.style.border = '2px solid #ef4444';
          card.style.boxShadow = '0 0 10px rgba(239,68,68,0.3)';
        }
      }
    });
    
    if (missingDocs.length > 0) {
      var docLabels = {
        'doc_aadhar': 'Aadhar Card',
        'doc_pan': 'PAN Card',
        'doc_cheque': 'Cancelled Cheque',
        'doc_sign': 'Signature',
        'doc_selfie': 'Selfie'
      };
      
      var missingList = missingDocs.map(function(d) { return docLabels[d]; }).join(', ');
      showToast('Please upload all required documents: ' + missingList);
      _setBtnState(false);
      
      // Scroll to first missing document
      var firstMissingCard = document.getElementById('ucard_' + missingDocs[0].replace('doc_', ''));
      if (firstMissingCard) {
        firstMissingCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }
    
    // Remove red borders if all files are present
    requiredDocs.forEach(function(docKey) {
      var card = document.getElementById('ucard_' + docKey.replace('doc_', ''));
      if (card) {
        card.style.border = '';
        card.style.boxShadow = '';
      }
    });

    var docCount  = Object.keys(_uploadedFiles).length;
    var docNames  = Object.keys(_uploadedFiles).map(function(k) {
      var lm = { doc_aadhar:'Aadhar Card', doc_pan:'PAN Card',
                 doc_cheque:'Cancelled Cheque', doc_sign:'Signature', doc_selfie:'Selfie' };
      return lm[k] || k;
    }).join(', ') || 'None';

    _setBtnState(true);

    /* â”€â”€ Try EmailJS first (works from file:// AND from server) â”€â”€ */
    var cfg = window._EJSCONFIG;
    if (cfg && cfg.ready) {
      var templateParams = {
        portfolio:       portfolio,
        applicant_name:  name,
        email:           email,
        mobile:          mobile,
        nominee_name:    nomName,
        nominee_pan:     nomPAN,
        nominee_dob:     nomDOB,
        nominee_mobile:  nomMob,
        docs_uploaded:   docCount + ' file(s): ' + docNames,
        submitted_at:    new Date().toLocaleString('en-IN', {timeZone:'Asia/Kolkata'}),
        reply_to:        email
      };

      emailjs.send(cfg.serviceId, cfg.templateId, templateParams)
        .then(function() {
          clearRegState();
          _setBtnState(false);
          _showSuccess(name);
        })
        .catch(function(err) {
          _setBtnState(false);
          console.error('EmailJS error:', err);
          showSecurityModal('Connection Error', 'Could not send automatically â€” please email us at whiteflowsint@gmail.com');
        });
      return;
    }

    /* Generate PDF in browser (jsPDF) then submit to server */
    var serverUrl = 'https://whiteflows.amburax.workers.dev/submit';

    var pdf_base64 = '';
    try {
      var appId = 'WF-' + new Date().toISOString().replace(/[^0-9]/g,'').slice(0,14);
      var jsPDF = window.jspdf ? window.jspdf.jsPDF : (window.jsPDF || null);
      if (jsPDF) {
        var doc = new jsPDF({ unit: 'mm', format: 'a4' });
        var GOLD = [212,168,83], INK = [14,13,11], IVORY = [248,247,243], GREY = [150,150,150], LG = [230,230,230];
        doc.setFillColor(IVORY[0],IVORY[1],IVORY[2]); doc.rect(0,0,210,297,'F');
        doc.setDrawColor(GOLD[0],GOLD[1],GOLD[2]); doc.line(10,10,200,10); doc.line(10,50,200,50);
        doc.setFont('helvetica','bold'); doc.setFontSize(22);
        doc.setTextColor(GOLD[0],GOLD[1],GOLD[2]);
        doc.text('CERTIFICATE OF APPLICATION',200,38,{align:'right'});
        doc.setFont('helvetica','normal'); doc.setFontSize(12); doc.setTextColor(INK[0],INK[1],INK[2]);
        doc.text('Application ID: '+appId,10,62);
        var now=new Date(), months=['January','February','March','April','May','June','July','August','September','October','November','December'];
        var ds=now.getDate()+' '+months[now.getMonth()]+' '+now.getFullYear()+', '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
        doc.text('Date: '+ds,10,72);
        var rows2=[['Portfolio Choice',portfolio||'N/A'],['Applicant Name',name||'N/A'],['Email Address',email||'N/A'],['Mobile Number',mobile||'N/A'],['Nominee Name',nomName||'N/A'],['Nominee PAN',nomPAN||'N/A']];
        var y=85;
        rows2.forEach(function(r){
          doc.setFillColor(255,255,255); doc.setDrawColor(LG[0],LG[1],LG[2]);
          doc.rect(10,y,50,12,'FD'); doc.rect(60,y,140,12,'FD');
          doc.setFont('helvetica','bold'); doc.setFontSize(9); doc.setTextColor(120,120,120);
          doc.text(r[0],12,y+8);
          doc.setFont('helvetica','normal'); doc.setTextColor(INK[0],INK[1],INK[2]);
          doc.text(String(r[1]).substring(0,50),62,y+8); y+=12;
        });
        doc.setFont('helvetica','italic'); doc.setFontSize(9); doc.setTextColor(GREY[0],GREY[1],GREY[2]);
        var ft='This is a computer-generated confirmation of your application to WhiteFlows International. Our advisory desk will review your documents and verify your identity within 24 working hours.';
        doc.text(doc.splitTextToSize(ft,190),10,y+20);
        doc.setDrawColor(GOLD[0],GOLD[1],GOLD[2]); doc.line(10,280,200,280);
        doc.setFont('helvetica','bold'); doc.setFontSize(8); doc.setTextColor(GOLD[0],GOLD[1],GOLD[2]);
        doc.text('WHITEFLOWS INTERNATIONAL â€” INVESTMENT ADVISORY',105,286,{align:'center'});
        pdf_base64 = doc.output('datauristring');
      }
    } catch(pdfErr) { console.warn('PDF gen (non-critical):',pdfErr); }

    var payload = {
      // app_id is now generated by the server for professional sequencing
      portfolio: portfolio, applicant_name: name,
      email: email, mobile: mobile,
      nominee_name: nomName, nominee_pan: nomPAN,
      nominee_dob: nomDOB, nominee_mobile: nomMob,
      submitted_at: new Date().toISOString(),
      pdf_base64: pdf_base64,
      documents: _uploadedFiles
    };

    fetch(serverUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function(res) { if (!res.ok) throw new Error('Server returned '+res.status); return res.json(); })
    .then(function(data) {
      _setBtnState(false);
      if (data.success) { _showSuccess(name); }
      else { showSecurityModal('Submission Error', 'Application saved but email failed: '+(data.error||'Unknown')); }
    })
    .catch(function(err) {
      _setBtnState(false);
      console.error('Submission error:', err);
      var isRateLimit = err.message.includes('429');
      var title = isRateLimit ? 'Security Limit Reached' : 'Connection Error';
      var msg = isRateLimit ? 'To protect our premium infrastructure, we limit submissions to 4 per hour. Please try again shortly.' : 'Could not connect to our secure server. Please ensure your internet is stable and try again.';
      showSecurityModal(title, msg);
    });
    return;
  }

  
  /* 
     â•â• OCEAN ECOSYSTEM FORM LOGIC â•â•
  */
  document.addEventListener('DOMContentLoaded', function() {
    const oceanForm = document.getElementById('oceanInvestorForm');
    const rangeSlider = document.getElementById('oceanRangeSlider');
    const rangeLabel = document.getElementById('oceanRangeLabel');
    const interestGrid = document.getElementById('oceanInterestGrid');
    const submitBtn = document.getElementById('oceanSubmitBtn');

    // Range Logic
    const ranges = ['â‚¹ 5-10 L', 'â‚¹ 10-25 L', 'â‚¹ 25-50 L', 'â‚¹ 50 L - 1 Cr', 'â‚¹ 1 Cr - 5 Cr', 'â‚¹ 5 Cr+'];
    if (rangeSlider && rangeLabel) {
      rangeSlider.addEventListener('input', (e) => {
        rangeLabel.textContent = ranges[e.target.value];
      });
    }

    // Interest Selection
    let selectedInterest = 'Equities';
    if (interestGrid) {
      interestGrid.querySelectorAll('.ocean-select-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          interestGrid.querySelectorAll('.ocean-select-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          selectedInterest = btn.dataset.val;
        });
      });
    }

    // Submission
    if (oceanForm) {
      oceanForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('oceanName').value.trim();
        const location = document.getElementById('oceanLocation').value.trim();
        const mobile = document.getElementById('oceanMobile').value.trim();
        const range = ranges[rangeSlider.value];

        if (!name || !location || !isValidPhone(mobile)) {
          showToast(isValidPhone(mobile) ? 'Please fill all fields.' : 'Enter a valid 10-digit mobile.');
          return;
        }

        submitBtn.disabled = true;
        submitBtn.classList.add('loading');

        const payload = {
          type: 'ocean_investor',
          form_name: 'WhiteFlows Ocean Registration',
          name: name,
          mobile: mobile,
          email: 'not-collected@ocean.wf', // Mandatory for backend, but we'll flag it
          location: location,
          interest: selectedInterest,
          investment_range: range
        };

        try {
          const resp = await fetch('https://whiteflows.amburax.workers.dev/submit-lead', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await resp.json();
          
          if (data.success) {
            showToast('Ocean Registration Successful! Ref: ' + data.ref_id);
            oceanForm.reset();
            rangeSlider.value = 2;
            rangeLabel.textContent = ranges[2];
            interestGrid.querySelectorAll('.ocean-select-btn').forEach(b => b.classList.remove('active'));
            interestGrid.querySelector('[data-val="Equities"]').classList.add('active');
            selectedInterest = 'Equities';
          } else {
            throw new Error(data.message || 'Submission failed');
          }
        } catch (err) {
          console.error(err);
          showToast('Connectivity issue. Please try again or WhatsApp us.');
        } finally {
          submitBtn.disabled = false;
          submitBtn.classList.remove('loading');
        }
      });
    }
  });

  document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeRegModal(); });

/**
 * REFINED WORKING HOURS LOGIC
 * Monday -Saturday, 9 AM - 6 PM IST
 */
function updateEliteSupportStatus() {
  const now = new Date();
  // Adjust to IST (UTC+5:30)
  const offset = 5.5 * 60 * 60 * 1000;
  const istDate = new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + offset);
  
  const day = istDate.getDay(); 
  const hour = istDate.getHours();
  const isActive = (day >= 1 && day <= 6) && (hour >= 9 && hour < 18);

  const dot = document.getElementById('wa-status-dot');
  const text = document.getElementById('wa-status-text');
  const btn = document.getElementById('float-wa');

  if (isActive) {
    dot.className = 'status-online';
    text.textContent = '(Online)';
    btn.dataset.offline = "false";
    btn.style.filter = 'none';
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  } else {
    dot.className = 'status-offline';
    text.textContent = '(Offline)';
    btn.dataset.offline = "true";
    btn.style.filter = 'grayscale(0.9)';
    btn.style.opacity = '0.7';
    btn.style.cursor = 'not-allowed';
  }
}

// Intercept click to show info if offline
document.getElementById('float-wa').addEventListener('click', function(e) {
  if (this.dataset.offline === "true") {
    e.preventDefault(); // STRICT BLOCK
    showToast('Support is currently Offline. (Working Hours: Monday -Saturday, 9AM-6PM IST)');
  }
});

// Run on init
document.addEventListener('DOMContentLoaded', () => {
  updateEliteSupportStatus();
  // Check every minute
  setInterval(updateEliteSupportStatus, 60000);
});

const themeToggleBtn = document.getElementById('themeToggle');
  const htmlEl = document.documentElement;
  
  // Load saved theme or default to light
  const currentTheme = localStorage.getItem('theme') || 'light';
  if (currentTheme === 'dark') {
    htmlEl.setAttribute('data-theme', 'dark');
  }
  
  themeToggleBtn.addEventListener('click', () => {
    const isDark = htmlEl.getAttribute('data-theme') === 'dark';
    if (isDark) {
      htmlEl.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    } else {
      htmlEl.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    }
  });

// Initialize AOS after DOM is ready and first paint is done
  if(document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      requestAnimationFrame(function() {
        AOS.init({ duration: 800, easing: 'ease-out-cubic', once: true, offset: 50 });
      });
    });
  } else {
    requestAnimationFrame(function() {
      AOS.init({ duration: 800, easing: 'ease-out-cubic', once: true, offset: 50 });
    });
  }

(function() {
  function onClick(event) {
    const trigger = event.target.closest('[data-click]');
    if (!trigger) return;

    const action = trigger.dataset.click;
    if (trigger.dataset.preventDefault === 'true') {
      event.preventDefault();
    }

    switch (action) {
      case 'carousel-move':
        carouselMove(Number(trigger.dataset.dir || 0));
        break;
      case 'carousel-go':
        carouselGoTo(Number(trigger.dataset.index || 0));
        break;
      case 'switch-tab':
        switchTab(trigger.dataset.tab || 'retail');
        break;
      case 'open-consult':
        openConsultModal(trigger.dataset.tab || 'retail');
        break;
      case 'open-portfolio':
        openPortfolioModal(trigger.dataset.portfolio || 'samyak');
        break;
      case 'open-reg':
        openRegModal(trigger.dataset.label || undefined);
        break;
      case 'reset-form':
        resetForm(trigger.dataset.form || 'retail');
        break;
      case 'submit-form':
        ({
          retail: submitRetail,
          project: submitProject,
          scale: submitScale,
          ocean: submitOcean,
          institutional: submitInstitutional,
        }[trigger.dataset.form || 'retail'] || function() {})();
        break;
      case 'reg-step':
        changeRegStep(Number(trigger.dataset.step || 0));
        break;
      case 'close-send':
        closeSendModal();
        break;
      case 'close-security':
        closeSecurityModal();
        break;
      case 'close-reg':
        closeRegModal();
        break;
      case 'close-portfolio':
        closePortfolioModal();
        break;
      case 'close-reg-overlay':
        closeRegOnBg(event);
        break;
      case 'close-pf-overlay':
        closePfModalOnBg(event);
        break;
      case 'send-choice':
        if (trigger.dataset.channel === 'whatsapp') doSendWhatsApp();
        if (trigger.dataset.channel === 'email') doSendEmail();
        break;
      case 'scroll-to': {
        const target = document.getElementById(trigger.dataset.target || '');
        if (target) target.scrollIntoView({ behavior: 'smooth' });
        break;
      }
      case 'scroll-top':
        window.scrollTo({ top: 0, behavior: 'smooth' });
        break;
    }
  }

  function onChange(event) {
    const target = event.target.closest('[data-change]');
    if (!target) return;

    const action = target.dataset.change;
    if (action === 'ocean-other') {
      toggleOceanOther(target.value);
      return;
    }
    if (action === 'upload') {
      handleUpload(target, target.dataset.card, target.dataset.status, target.dataset.preview);
    }
  }

  function onSubmit(event) {
    const form = event.target.closest('[data-submit="reg-form"]');
    if (!form) return;
    submitRegForm(event);
  }

  document.addEventListener('click', onClick);
  document.addEventListener('change', onChange);
  document.addEventListener('submit', onSubmit);
})();
