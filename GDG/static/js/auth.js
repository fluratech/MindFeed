document.addEventListener('DOMContentLoaded', () => {
    // Helper to show message
    const showMessage = (text, type = 'error') => {
        const msgEl = document.getElementById('message');
        if (!msgEl) return;
        msgEl.textContent = text;
        msgEl.className = `message ${type}`;
    };

    // Generic generic form handler
    const handleAuth = async (formId, url) => {
        const form = document.getElementById(formId);
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button');
            const originalText = btn.textContent;

            // Basic Frontend Validation for Register
            if (formId === 'register-form') {
                const password = form.password.value;
                const confirm = form.confirm_password.value;
                if (password !== confirm) {
                    showMessage("Passwords do not match");
                    return;
                }
            }

            try {
                btn.classList.add('loading');
                btn.disabled = true;

                // Collect data
                // Collect data
                const formData = new FormData(form);
                const data = Object.fromEntries(formData.entries());

                // Handle multi-select checkboxes (e.g., topics)
                const topics = formData.getAll('topics');
                if (topics.length > 0) {
                    data.topics = topics;
                }

                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await res.json();

                if (res.ok) {
                    showMessage("Success!", 'success');
                    if (result.redirect) {
                        window.location.href = result.redirect;
                    }
                } else {
                    showMessage(result.message || "An error occurred");
                    btn.classList.remove('loading');
                    btn.textContent = originalText;
                    btn.disabled = false;
                }

            } catch (err) {
                console.error(err);
                showMessage("Network error. Please try again.");
                btn.classList.remove('loading');
                btn.textContent = originalText;
                btn.disabled = false;
            }
        });
    };

    handleAuth('login-form', '/auth/login');
    handleAuth('register-form', '/auth/register');
});
