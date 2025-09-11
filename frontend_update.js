    // Single snapshot function - gets image and runs OCR in one call
    setTimeout(() => {
      const indexEl = document.getElementById("ocrIndex");
      const statusEl = document.getElementById("ocrStatus");
      const img = document.getElementById("webcamImage");
      const loading = document.getElementById("webcamLoading");
      
      // Show loading state
      loading.style.display = "block";
      loading.textContent = "Taking snapshot & analyzing...";
      img.style.display = "none";
      statusEl.textContent = "Processing...";
      statusEl.style.color = "#ffa726";
      
      // Single call to /snapshot - gets image and OCR results
      fetch("/snapshot")
        .then(response => response.json())
        .then(data => {
          // Display the image from response
          if (data.image) {
            img.src = data.image;
            img.style.display = "block";
            loading.style.display = "none";
          }
          
          // Display OCR results
          if (data.success) {
            indexEl.textContent = "Index: " + data.index;
            statusEl.textContent = data.engine + " - Success";
            statusEl.style.color = "#4caf50";
          } else {
            indexEl.textContent = "Index: -----";
            statusEl.textContent = data.error || "OCR failed";
            statusEl.style.color = "#f44336";
          }
          
          console.log("Snapshot + OCR Result:", data);
        })
        .catch(error => {
          console.error("Snapshot Error:", error);
          loading.textContent = "Snapshot failed";
          loading.style.color = "#f44336";
          statusEl.textContent = "Connection error";
          statusEl.style.color = "#f44336";
        });
    }, 2000); // Start after 2 seconds
