// Auto-dismiss alerts after 4 seconds with smooth fade-out animation
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');

    alerts.forEach(function(alert) {
        // Add fade-out animation after 4 seconds
        setTimeout(function() {
            // Start fade out
            alert.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';

            // Remove from DOM after animation completes
            setTimeout(function() {
                alert.remove();
            }, 500);
        }, 4000);
    });

    // Allow manual dismissal if alert has close button
    const closeButtons = document.querySelectorAll('.alert .btn-close');
    closeButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const alert = this.closest('.alert');
            alert.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';

            setTimeout(function() {
                alert.remove();
            }, 300);
        });
    });
});
