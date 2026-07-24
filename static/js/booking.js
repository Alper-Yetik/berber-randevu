const serviceRadios = document.querySelectorAll('.service-radio');
const dateInput     = document.getElementById('dateInput');
const slotsContainer = document.getElementById('slotsContainer');
const selectedTimeInput = document.getElementById('selectedTime');
const closedMsg     = document.getElementById('closedMsg');

function getSelectedService() {
  const checked = document.querySelector('.service-radio:checked');
  return checked ? checked.value : null;
}

function loadSlots() {
  const service = getSelectedService();
  const date    = dateInput.value;

  if (!service || !date) {
    slotsContainer.innerHTML = '<p class="text-muted text-center py-3"><i class="bi bi-arrow-up-circle me-1"></i>Önce hizmet ve tarih seçin.</p>';
    selectedTimeInput.value = '';
    return;
  }

  slotsContainer.innerHTML = '<p class="text-muted text-center py-3"><i class="bi bi-hourglass-split me-1"></i>Saatler yükleniyor…</p>';
  closedMsg.classList.add('d-none');

  fetch(`/musait-saatler?tarih=${date}&hizmet=${encodeURIComponent(service)}`)
    .then(r => r.json())
    .then(data => {
      if (data.kapali) {
        closedMsg.classList.remove('d-none');
        slotsContainer.innerHTML = '';
        return;
      }

      closedMsg.classList.add('d-none');

      if (!Array.isArray(data) || data.length === 0) {
        slotsContainer.innerHTML = '<p class="text-warning text-center py-3"><i class="bi bi-calendar-x me-1"></i>Bu gün için müsait saat yok.</p>';
        return;
      }

      slotsContainer.innerHTML = '<div class="pb-2">' +
        data.map(slot =>
          `<span class="time-slot" data-time="${slot}" onclick="selectTime(this)">${slot}</span>`
        ).join('') +
        '</div>';

      selectedTimeInput.value = '';
    })
    .catch(() => {
      slotsContainer.innerHTML = '<p class="text-danger text-center py-3">Saatler yüklenemedi.</p>';
    });
}

function selectTime(el) {
  document.querySelectorAll('.time-slot').forEach(s => s.classList.remove('selected'));
  el.classList.add('selected');
  selectedTimeInput.value = el.dataset.time;
}

serviceRadios.forEach(r => r.addEventListener('change', loadSlots));
dateInput.addEventListener('change', loadSlots);
