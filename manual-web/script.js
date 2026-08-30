document.addEventListener('DOMContentLoaded', () => {
  // Theme Switching Logic
  const themeToggle = document.getElementById('theme-toggle');
  const body = document.body;

  // Retrieve saved theme or default to system scheme
  const savedTheme = localStorage.getItem('theme') || 'light';
  body.className = savedTheme === 'dark' ? 'dark-mode' : 'light-mode';

  themeToggle.addEventListener('click', () => {
    if (body.classList.contains('light-mode')) {
      body.classList.replace('light-mode', 'dark-mode');
      localStorage.setItem('theme', 'dark');
    } else {
      body.classList.replace('dark-mode', 'light-mode');
      localStorage.setItem('theme', 'light');
    }
  });

  // Navigation Links / Tab Switching
  const navLinks = document.querySelectorAll('.nav-link');
  const docSections = document.querySelectorAll('.doc-section');

  function switchSection(targetId) {
    // Remove active class from all sections & links
    docSections.forEach(section => section.classList.remove('active-section'));
    navLinks.forEach(link => link.classList.remove('active'));

    // Add active class to target section
    const targetSection = document.getElementById(targetId);
    if (targetSection) {
      targetSection.classList.add('active-section');
      
      // Find corresponding navigation link and highlight it
      const correspondingLink = document.querySelector(`.nav-link[href="#${targetId}"]`);
      if (correspondingLink) {
        correspondingLink.classList.add('active');
      }
      
      // Scroll smoothly to top of content area on desktop
      if (window.innerWidth > 1024) {
        document.querySelector('.content-area').scrollTop = 0;
      } else {
        targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('href').substring(1);
      switchSection(targetId);
      // Update hash in URL
      history.pushState(null, null, `#${targetId}`);
    });
  });

  // Handle URL hash on page load
  const currentHash = window.location.hash.substring(1);
  if (currentHash) {
    switchSection(currentHash);
  }

  // Interactive Lightbox for screenshots
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightbox-img');
  const lightboxCaption = document.getElementById('lightbox-caption');
  const closeBtn = document.querySelector('.lightbox-close');
  const triggers = document.querySelectorAll('.lightbox-trigger');

  triggers.forEach(trigger => {
    trigger.addEventListener('click', () => {
      lightbox.style.display = 'block';
      lightboxImg.src = trigger.src;
      lightboxCaption.textContent = trigger.alt;
      document.body.style.overflow = 'hidden'; // Lock background scroll
    });
  });

  function closeLightbox() {
    lightbox.style.display = 'none';
    document.body.style.overflow = 'auto'; // Unlock scroll
  }

  closeBtn.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', (e) => {
    if (e.target !== lightboxImg && e.target !== lightboxCaption) {
      closeLightbox();
    }
  });

  // Search Filtering
  const searchInput = document.getElementById('doc-search');
  searchInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    if (!term) {
      // Clear filters, show current active section
      const activeLink = document.querySelector('.nav-link.active');
      if (activeLink) {
        const activeId = activeLink.getAttribute('href').substring(1);
        switchSection(activeId);
      }
      return;
    }

    // Filter content
    docSections.forEach(section => {
      const text = section.innerText.toLowerCase();
      const match = text.includes(term);
      if (match) {
        section.classList.add('active-section');
      } else {
        section.classList.remove('active-section');
      }
    });
  });
});
