// Comprehensive Form Debugging Script
console.log('🔍 Form Debug Script Loaded');

// Global form monitoring
document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 Setting up form monitoring...');
    
    // Monitor all forms
    const forms = document.querySelectorAll('form');
    console.log(`Found ${forms.length} forms on the page`);
    
    forms.forEach((form, index) => {
        console.log(`📝 Form ${index + 1}:`, {
            action: form.action,
            method: form.method,
            id: form.id,
            class: form.className
        });
        
        // Monitor form submission WITHOUT interfering
        form.addEventListener('submit', function(e) {
            console.log(`🚀 Form ${index + 1} submission started`);
            console.log('Form details:', {
                action: this.action,
                method: this.method,
                formData: new FormData(this)
            });
            
            // Don't prevent default - just monitor
            console.log('✅ Allowing form to submit normally');
        });
        
        // Monitor form field changes
        const inputs = this.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                console.log(`📝 Input changed: ${this.name} = ${this.value}`);
            });
        });
    });
    
    // Monitor page load/unload
    window.addEventListener('load', function() {
        console.log('📄 Page fully loaded');
    });
    
    window.addEventListener('beforeunload', function() {
        console.log('🔄 Page is about to unload');
    });
    
    // Monitor errors
    window.addEventListener('error', function(e) {
        console.log('❌ JavaScript Error:', e.error);
    });
    
    // Monitor unhandled promise rejections
    window.addEventListener('unhandledrejection', function(e) {
        console.log('❌ Unhandled Promise Rejection:', e.reason);
    });
    
    console.log('✅ Form monitoring setup complete');
});

// Utility function to check form status
function checkFormStatus() {
    const forms = document.querySelectorAll('form');
    console.log(`📊 Current form status: ${forms.length} forms found`);
    
    forms.forEach((form, index) => {
        const submitButton = form.querySelector('button[type="submit"]');
        console.log(`Form ${index + 1}:`, {
            valid: form.checkValidity(),
            submitButtonDisabled: submitButton ? submitButton.disabled : 'No button',
            submitButtonText: submitButton ? submitButton.innerHTML : 'No button'
        });
    });
}

// Make function globally available
window.checkFormStatus = checkFormStatus; 