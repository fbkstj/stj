(() => {
    const carousel = document.getElementById("mastheadCarousel");
    const layers = Array.from(carousel.querySelectorAll("img"));
    const toggle = carousel.querySelector("button");
    const slides = [
        "01-realistic-circuit-and-title-subtitle-kai.webp",
        "02-blueprint-wide-title-subtitle-kai.webp",
        "03-isometric-wide-title-subtitle-kai.webp",
        "04-watercolor-wide-title-subtitle-kai.webp",
        "05-minimal-wide-title-subtitle-kai.webp",
        "06-retro-wide-title-subtitle-kai.webp",
        "07-quantum-wide-title-subtitle-kai.webp"
    ];
    const directory = new URL(".", document.currentScript.src);
    let visible = 0;
    let current = -1;
    let revision = 0;
    let timer;
    let paused = false;

    function updateToggle() {
        toggle.textContent = paused ? (current < 0 ? "播放動畫" : "繼續輪播") : "暫停輪播";
    }

    function schedule() {
        clearTimeout(timer);
        if (!paused && !document.hidden) {
            timer = setTimeout(advance, current < 0 ? 0 : 15000);
        }
    }

    async function advance() {
        const next = (current + 1) % slides.length;
        const incoming = layers[1 - visible];
        const pending = revision;
        incoming.src = new URL(slides[next], directory).href;
        try {
            await incoming.decode();
        } catch {
            if (pending === revision) {
                timer = setTimeout(advance, 15000);
            }
            return;
        }
        if (pending !== revision || paused || document.hidden) return;

        incoming.classList.add("is-visible");
        layers[visible].classList.remove("is-visible");
        visible = 1 - visible;
        current = next;
        schedule();

        const preload = new Image();
        preload.src = new URL(slides[(current + 1) % slides.length], directory).href;
    }

    toggle.addEventListener("click", () => {
        revision++;
        paused = !paused;
        updateToggle();
        schedule();
    });
    document.addEventListener("visibilitychange", () => {
        revision++;
        schedule();
    });
    toggle.hidden = false;
    updateToggle();
    schedule();
})();
