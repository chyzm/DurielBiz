function debounce(fn, waitMs = 200) {
    let timeoutId;
    return function debounced(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), waitMs);
    };
}

function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove('hidden');
    modalEl.classList.add('animate-fade-in-up');
}

function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add('hidden');
}
