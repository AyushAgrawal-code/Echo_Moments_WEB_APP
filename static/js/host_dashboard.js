
// Host Dashboard JavaScript
let uploadsEnabled = true;
let eventData = {
    name: "Wedding Reception",
    code: "ABC123",
    totalPhotos: 24,
    totalGuests: 8,
    recentUploads: 3,
    startTime: new Date(Date.now() - 2 * 60 * 60 * 1000) // 2 hours ago
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    updateStats();
    setupDragAndDrop();
    updateEventDuration();
    setInterval(updateEventDuration, 60000); // Update every minute
});

// Update statistics
function updateStats() {
    document.getElementById('totalPhotos').textContent = eventData.totalPhotos;
    document.getElementById('totalGuests').textContent = eventData.totalGuests;
    document.getElementById('recentUploads').textContent = eventData.recentUploads;
    updateEventDuration();
}

// Update event duration
function updateEventDuration() {
    const now = new Date();
    const diff = now - eventData.startTime;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    document.getElementById('eventDuration').textContent = `${hours}h ${minutes}m`;
}

// Handle host file upload
function handleHostUpload(input) {
    const files = Array.from(input.files);
    console.log('Host uploading files:', files.length);
    
    if (files.length > 0) {
        files.forEach(file => {
            if (file.type.startsWith('image/')) {
                console.log('Processing image:', file.name);
                // Simulate upload
                eventData.totalPhotos++;
            }
        });
        
        updateStats();
        showToast('Photos uploaded successfully!', 'success');
        input.value = ''; // Clear the input
    }
}

// Setup drag and drop
function setupDragAndDrop() {
    const uploadArea = document.querySelector('.upload-area');
    
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('dragging');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
        
        const files = Array.from(e.dataTransfer.files);
        const imageFiles = files.filter(file => file.type.startsWith('image/'));
        
        if (imageFiles.length > 0) {
            handleHostUpload({ files: imageFiles });
        }
    });
}

// Toggle uploads
function toggleUploads() {
    uploadsEnabled = !uploadsEnabled;
    const button = document.getElementById('uploadStatus');
    button.textContent = uploadsEnabled ? 'Disable Uploads' : 'Enable Uploads';
    
    showToast(
        uploadsEnabled ? 'Guest uploads enabled' : 'Guest uploads disabled',
        'info'
    );
}

// View guest photos
function viewGuestPhotos(guestId) {
    console.log('Viewing photos for guest:', guestId);
    
    const modal = document.getElementById('guestPhotosModal');
    const modalTitle = document.getElementById('modalGuestName');
    const modalGrid = document.getElementById('modalPhotoGrid');
    
    // Sample data
    const guestNames = {
        'sarah': 'Sarah Johnson',
        'mike': 'Mike Chen',
        'emily': 'Emily Davis'
    };
    
    const samplePhotos = [
        'https://images.unsplash.com/photo-1469371670807-013ccf25f16a?w=400&h=400&fit=crop',
        'https://images.unsplash.com/photo-1511285560929-80b456fea0bc?w=400&h=400&fit=crop',
        'https://images.unsplash.com/photo-1465495976277-4387d4b0e4a6?w=400&h=400&fit=crop',
        'https://images.unsplash.com/photo-1583939003579-730e3918a45a?w=400&h=400&fit=crop'
    ];
    
    modalTitle.textContent = `${guestNames[guestId]}'s Photos`;
    modalGrid.innerHTML = '';
    
    samplePhotos.forEach((src, index) => {
        const photoDiv = document.createElement('div');
        photoDiv.className = 'photo-item';
        photoDiv.innerHTML = `
            <img src="${src}" alt="Guest photo ${index + 1}">
            <div class="photo-overlay">
                <p>Photo ${index + 1}</p>
            </div>
        `;
        modalGrid.appendChild(photoDiv);
    });
    
    modal.classList.add('active');
}

// Remove guest
function removeGuest(guestId) {
    if (confirm('Are you sure you want to remove this guest from the event?')) {
        console.log('Removing guest:', guestId);
        eventData.totalGuests--;
        updateStats();
        showToast('Guest removed from event', 'info');
        
        // Remove guest from UI
        const guestItems = document.querySelectorAll('.guest-item');
        guestItems.forEach(item => {
            if (item.textContent.toLowerCase().includes(guestId)) {
                item.remove();
            }
        });
    }
}

// Save settings
function saveSettings() {
    const uploadLimit = document.getElementById('uploadLimit').value;
    const autoApprove = document.getElementById('autoApprove').value;
    
    console.log('Saving settings:', { uploadLimit, autoApprove });
    showToast('Settings saved successfully!', 'success');
}

// Quick actions
function downloadAllPhotos() {
    console.log('Downloading all photos...');
    showToast('Preparing download... This may take a moment.', 'info');
    
    // Simulate download preparation
    setTimeout(() => {
        showToast('Download started! Check your downloads folder.', 'success');
    }, 2000);
}

function shareEventLink() {
    const eventLink = `https://echomoments.com/join/${eventData.code}`;
    
    if (navigator.share) {
        navigator.share({
            title: 'Join my EchoMoments event',
            text: `Join "${eventData.name}" on EchoMoments!`,
            url: eventLink
        });
    } else if (navigator.clipboard) {
        navigator.clipboard.writeText(eventLink);
        showToast('Event link copied to clipboard!', 'success');
    } else {
        prompt('Copy this link to share your event:', eventLink);
    }
}

function generateQRCode() {
    console.log('Generating QR code for event:', eventData.code);
    showToast('QR code generated! Opening in new window...', 'info');
    
    // In a real app, this would generate and display a QR code
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=https://echomoments.com/join/${eventData.code}`;
    window.open(qrUrl, '_blank');
}

function exportGuestList() {
    console.log('Exporting guest list...');
    
    const guestData = [
        'Guest Name,Photos Uploaded,Status',
        'Sarah Johnson,4,Online',
        'Mike Chen,7,Online',
        'Emily Davis,2,Offline'
    ].join('\n');
    
    const blob = new Blob([guestData], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${eventData.name}-guest-list.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    
    showToast('Guest list exported successfully!', 'success');
}

function inviteGuests() {
    const email = prompt('Enter guest email address:');
    if (email && email.includes('@')) {
        console.log('Inviting guest:', email);
        showToast(`Invitation sent to ${email}!`, 'success');
    }
}

function endEvent() {
    if (confirm('Are you sure you want to end this event? This action cannot be undone.')) {
        console.log('Ending event...');
        showToast('Event ended. Redirecting to summary...', 'info');
        
        setTimeout(() => {
            window.location.href = 'event-summary.html';
        }, 2000);
    }
}

function signOut() {
    if (confirm('Are you sure you want to sign out?')) {
        console.log('Signing out...');
        window.location.href = 'index.html';
    }
}

// Close modal
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Toast notification system
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        background: ${type === 'success' ? 'var(--echo-emerald)' : type === 'error' ? '#EF4444' : 'var(--echo-purple)'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--echo-radius);
        box-shadow: var(--echo-shadow);
        z-index: 1001;
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.3s ease;
    `;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 100);
    
    // Auto remove
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// Click outside modal to close
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});
