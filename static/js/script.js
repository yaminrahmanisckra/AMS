// Academic Management System - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Form validation enhancement (without interfering)
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Only add validation styling, don't prevent submission
            if (!form.checkValidity()) {
                form.classList.add('was-validated');
            }
        });
    });

    // Time validation for schedule form
    const startTimeInput = document.getElementById('start_time');
    const endTimeInput = document.getElementById('end_time');
    
    if (startTimeInput && endTimeInput) {
        endTimeInput.addEventListener('change', function() {
            const startTime = startTimeInput.value;
            const endTime = endTimeInput.value;
            
            if (startTime && endTime && startTime >= endTime) {
                endTimeInput.setCustomValidity('End time must be after start time');
                endTimeInput.classList.add('is-invalid');
            } else {
                endTimeInput.setCustomValidity('');
                endTimeInput.classList.remove('is-invalid');
            }
        });
    }

    // Search functionality for tables
    const searchInputs = document.querySelectorAll('.table-search');
    searchInputs.forEach(input => {
        input.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const table = this.closest('.card').querySelector('table');
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    });

    // Confirmation dialogs for delete actions
    const deleteButtons = document.querySelectorAll('.btn-outline-danger');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this item?')) {
                e.preventDefault();
            }
        });
    });

    // Tooltip initialization
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Popover initialization
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Smooth scrolling for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Auto-resize textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    // File input preview
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.createElement('img');
                    preview.src = e.target.result;
                    preview.style.maxWidth = '200px';
                    preview.style.maxHeight = '200px';
                    preview.classList.add('mt-2');
                    
                    const container = input.parentElement;
                    const existingPreview = container.querySelector('img');
                    if (existingPreview) {
                        existingPreview.remove();
                    }
                    container.appendChild(preview);
                };
                reader.readAsDataURL(file);
            }
        });
    });

    // Dynamic form fields
    const addFieldButtons = document.querySelectorAll('.add-field');
    addFieldButtons.forEach(button => {
        button.addEventListener('click', function() {
            const container = this.closest('.form-group');
            const fieldTemplate = container.querySelector('.field-template');
            const newField = fieldTemplate.cloneNode(true);
            newField.classList.remove('field-template');
            newField.style.display = 'block';
            
            // Update field names and IDs
            const inputs = newField.querySelectorAll('input, select, textarea');
            const fieldCount = container.querySelectorAll('.form-group:not(.field-template)').length;
            inputs.forEach(input => {
                const name = input.getAttribute('name');
                const id = input.getAttribute('id');
                if (name) {
                    input.setAttribute('name', name.replace('[0]', `[${fieldCount}]`));
                }
                if (id) {
                    input.setAttribute('id', id.replace('0', fieldCount));
                }
            });
            
            container.appendChild(newField);
        });
    });

    // Remove field functionality
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-field')) {
            const field = e.target.closest('.form-group');
            if (field && !field.classList.contains('field-template')) {
                field.remove();
            }
        }
    });

    // Print functionality
    const printButtons = document.querySelectorAll('.btn-print');
    printButtons.forEach(button => {
        button.addEventListener('click', function() {
            window.print();
        });
    });

    // Export functionality (placeholder)
    const exportButtons = document.querySelectorAll('.btn-export');
    exportButtons.forEach(button => {
        button.addEventListener('click', function() {
            alert('Export functionality will be implemented here');
        });
    });

    // Theme toggle (if implemented)
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-theme');
            const isDark = document.body.classList.contains('dark-theme');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        });
    }

    // Initialize theme from localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
    }

    console.log('Academic Management System initialized successfully!');
}); 