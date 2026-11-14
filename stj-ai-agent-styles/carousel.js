(() => {
    const carousel = document.getElementById("mastheadCarousel");
    const layers = Array.from(carousel.querySelectorAll("img"));
    const toggle = carousel.querySelector("button");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const slides = [
        "01-realistic-esp32.webp",
        "02-blueprint.webp",
        "03-isometric.webp",
        "04-watercolor.webp",
        "05-minimal.webp",
        "06-retro.webp",
        "07-quantum.webp"
    ];
    const directory = new URL(".", document.currentScript.src);
    const still = layers[0].src;
    let visible = 0;
    let current = -1;
    let revision = 0;
    let timer;
    let paused = false;

    function schedule() {
        clearTimeout(timer);
        if (!paused && !document.hidden && !reducedMotion.matches) {
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
        if (pending !== revision || paused || document.hidden || reducedMotion.matches) return;

        incoming.classList.add("is-visible");
        layers[visible].classList.remove("is-visible");
        visible = 1 - visible;
        current = next;
        schedule();

        const preload = new Image();
        preload.src = new URL(slides[(current + 1) % slides.length], directory).href;
    }

    function updateMotion() {
        revision++;
        toggle.hidden = reducedMotion.matches;
        if (reducedMotion.matches) {
            layers[visible].src = still;
            current = -1;
        }
        schedule();
    }

    toggle.addEventListener("click", () => {
        revision++;
        paused = !paused;
        toggle.textContent = paused ? "繼續輪播" : "暫停輪播";
        schedule();
    });
    document.addEventListener("visibilitychange", () => {
        revision++;
        schedule();
    });
    reducedMotion.addEventListener("change", updateMotion);
    updateMotion();
})();
