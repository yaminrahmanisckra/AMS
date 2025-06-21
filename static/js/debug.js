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
        
        // Monitor form submission
        form.addEventListener('submit', function(e) {
            console.log(`🚀 Form ${index + 1} submission started`);
            console.log('Form details:', {
                action: this.action,
                method: this.method,
                formData: new FormData(this)
            });
            
            // Check if form is valid
            if (!this.checkValidity()) {
                console.log('❌ Form validation failed');
                e.preventDefault();
                this.classList.add('was-validated');
                return;
            }
            
            console.log('✅ Form validation passed');
            
            // Monitor submit button
            const submitButton = this.querySelector('button[type="submit"]');
            if (submitButton) {
                console.log('🔘 Submit button found:', submitButton.textContent);
                
                // Check if button is already disabled
                if (submitButton.disabled) {
                    console.log('⚠️ Submit button already disabled');
                } else {
                    console.log('🔘 Enabling loading state on submit button');
                    submitButton.disabled = true;
                    const originalText = submitButton.innerHTML;
                    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                    
                    // Store original text for potential restoration
                    submitButton.dataset.originalText = originalText;
                }
            } else {
                console.log('⚠️ No submit button found in form');
            }
            
            // Let the form submit normally
            console.log('📤 Allowing form to submit normally');
        });
        
        // Monitor form field changes
        const inputs = this.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                console.log(`📝 Input changed: ${this.name} = ${this.value}`);
            });
            
            input.addEventListener('input', function() {
                console.log(`⌨️ Input typing: ${this.name} = ${this.value}`);
            });
        });
    });
    
    // Monitor AJAX requests
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        console.log('🌐 Fetch request:', args);
        return originalFetch.apply(this, args);
    };
    
    const originalXHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function() {
        const xhr = new originalXHR();
        xhr.addEventListener('load', function() {
            console.log('📡 XHR Response:', {
                status: this.status,
                responseText: this.responseText.substring(0, 200) + '...'
            });
        });
        return xhr;
    };
    
    // Monitor page unload
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