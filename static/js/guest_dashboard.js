
// Guest Dashboard JavaScript
let guestData = {
    name: "Sarah Johnson",
    eventName: "Wedding Reception",
    eventCode: "ABC123",
    myPhotos: 4,
    uploadLimit: 25,
    totalEventPhotos: 24,
    uploadedPhotos: []
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    updateStats();
    setupDragAndDrop();
    loadMyPhotos();
});

// Update statistics
function updateStats() {
    document.getElementById('guestName').textContent = guestData.name;
    document.getElementById('myPhotos').textContent = guestData.myPhotos;
    document.getElementById('uploadLimit').textContent = guestData.uploadLimit;
    document.getElementById('remainingUploads').textContent = guestData.uploadLimit - guestData.myPhotos;
    document.getElementById('totalEventPhotos').textContent = guestData.totalEventPhotos;
    document.getElementById('photosUploaded').textContent = guestData.myPhotos;
    document.getElementById('maxPhotos').textContent = guestData.uploadLimit;
}

// Handle guest file upload
function handleGuestUpload(input) {
    const files = Array.from(input.files);
    console.log('Guest uploading files:', files.length);
    
    if (files.length > 0) {
        const remainingSlots = guestData.uploadLimit - guestData.myPhotos;
        
        if (files.length > remainingSlots) {
            showToast(`You can only upload ${remainingSlots} more photos.`, 'error');
            return;
        }
        
        showUploadProgress();
        
        // Simulate upload process
        let uploaded = 0;
        const uploadFile = (index) => {
            if (index >= files.length) {
                hideUploadProgress();
                guestData.myPhotos += files.length;
                guestData.totalEventPhotos += files.length;
                updateStats();
                loadMyPhotos();
                showToast(`${files.length} photos uploaded successfully!`, 'success');
                input.value = '';
                return;
            }
            
            const file = files[index];
            if (file.type.startsWith('image/')) {
                updateUploadProgress((index + 1) / files.length * 100, `Uploading ${file.name}...`);
                
                // Add to uploaded photos
                const reader = new FileReader();
                reader.onload = function(e) {
                    guestData.uploadedPhotos.unshift({
                        src: e.target.result,
                        name: file.name,
                        timestamp: new Date(),
                        id: Date.now() + index
                    });
                    
                    setTimeout(() => uploadFile(index + 1), 500);
                };
                reader.readAsDataURL(file);
            } else {
                uploadFile(index + 1);
            }
        };
        
        uploadFile(0);
    }
}

// Setup drag and drop
function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');
    
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
            const fakeInput = { files: imageFiles };
            handleGuestUpload(fakeInput);
        }
    });
}

// Show upload progress
function showUploadProgress() {
    document.getElementById('uploadProgress').classList.remove('hidden');
}

// Hide upload progress
function hideUploadProgress() {
    document.getElementById('uploadProgress').classList.add('hidden');
    updateUploadProgress(0, '');
}

// Update upload progress
function updateUploadProgress(percentage, status) {
    document.getElementById('progressBar').style.width = percentage + '%';
    document.getElementById('uploadStatus').textContent = status;
}

// Load my photos
function loadMyPhotos() {
    const grid = document.getElementById('myPhotosGrid');
    
    // Sample photos for demo if no uploaded photos
    if (guestData.uploadedPhotos.length === 0) {
        const samplePhotos = [
            {
                src: 'https://images.unsplash.com/photo-1469371670807-013ccf25f16a?w=400&h=400&fit=crop&crop=faces',
                timestamp: new Date(Date.now() - 5 * 60 * 1000),
                id: 1
            },
            {
                src: 'https://images.unsplash.com/photo-1511285560929-80b456fea0bc?w=400&h=400&fit=crop&crop=faces',
                timestamp: new Date(Date.now() - 8 * 60 * 1000),
                id: 2
            },
            {
                src: 'https://images.unsplash.com/photo-1465495976277-4387d4b0e4a6?w=400&h=400&fit=crop&crop=faces',
                timestamp: new Date(Date.now() - 15 * 60 * 1000),
                id: 3
            },
            {
                src: 'https://images.unsplash.com/photo-1583939003579-730e3918a45a?w=400&h=400&fit=crop&crop=faces',
                timestamp: new Date(Date.now() - 20 * 60 * 1000),
                id: 4
            }
        ];
        guestData.uploadedPhotos = samplePhotos;
    }
    
    // Clear existing photos
    grid.innerHTML = '';
    
    // Add photos to grid
    guestData.uploadedPhotos.forEach(photo => {
        const photoDiv = document.createElement('div');
        photoDiv.className = 'photo-item';
        photoDiv.onclick = () => openPhotoModal(photo);
        
        const timeAgo = getTimeAgo(photo.timestamp);
        
        photoDiv.innerHTML = `
            <img src="${photo.src}" alt="My photo">
            <div class="photo-overlay">
                <p>Uploaded ${timeAgo}</p>
            </div>
        `;
        
        grid.appendChild(photoDiv);
    });
}

// Open photo modal
function openPhotoModal(photo) {
    const modal = document.getElementById('photoModal');
    const modalPhoto = document.getElementById('modalPhoto');
    
    modalPhoto.src = photo.src;
    modal.classList.add('active');
    
    // Store current photo for actions
    modal.currentPhoto = photo;
}

// Delete photo
function deletePhoto() {
    const modal = document.getElementById('photoModal');
    const photo = modal.currentPhoto;
    
    if (photo && confirm('Are you sure you want to delete this photo?')) {
        const index = guestData.uploadedPhotos.findIndex(p => p.id === photo.id);
        if (index > -1) {
            guestData.uploadedPhotos.splice(index, 1);
            guestData.myPhotos--;
            guestData.totalEventPhotos--;
            updateStats();
            loadMyPhotos();
            closeModal('photoModal');
            showToast('Photo deleted successfully', 'info');
        }
    }
}

// Download photo
function downloadPhoto() {
    const modal = document.getElementById('photoModal');
    const photo = modal.currentPhoto;
    
    if (photo) {
        const a = document.createElement('a');
        a.href = photo.src;
        a.download = photo.name || 'photo.jpg';
        a.click();
        showToast('Photo download started', 'success');
    }
}

// Clear all photos
function clearAllPhotos() {
    if (confirm('Are you sure you want to delete all your photos? This action cannot be undone.')) {
        const photoCount = guestData.uploadedPhotos.length;
        guestData.uploadedPhotos = [];
        guestData.myPhotos = 0;
        guestData.totalEventPhotos -= photoCount;
        updateStats();
        loadMyPhotos();
        showToast('All photos deleted', 'info');
    }
}

// Leave event
function leaveEvent() {
    if (confirm('Are you sure you want to leave this event? You will lose access to all photos.')) {
        console.log('Leaving event...');
        showToast('Leaving event...', 'info');
        
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 2000);
    }
}

// Close modal
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Utility function to get time ago
function getTimeAgo(timestamp) {
    const now = new Date();
    const diff = now - new Date(timestamp);
    const minutes = Math.floor(diff / (1000 * 60));
    
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes} min ago`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
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
