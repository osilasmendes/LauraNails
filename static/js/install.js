const installButton = document.getElementById("install-app");
let installPrompt;

window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    installButton.hidden = false;
});

installButton.addEventListener("click", async () => {
    if (!installPrompt) return;
    const prompt = installPrompt;
    installPrompt = undefined;
    installButton.hidden = true;

    try {
        await prompt.prompt();
    } catch {
        // The browser menu remains available if the install prompt expires.
    }
});

window.addEventListener("appinstalled", () => {
    installPrompt = undefined;
    installButton.hidden = true;
});
