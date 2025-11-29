const API_BASE = "http://localhost:4000";

let storeIdA, storeIdB, filenameA, filenameB;

document.getElementById("uploadBtn").onclick = async () => {
    const fileA = document.getElementById("fileA").files[0];
    const fileB = document.getElementById("fileB").files[0];

    if (!fileA || !fileB) {
        alert("Please upload both PDFs");
        return;
    }

    document.getElementById("uploadStatus").innerText = "Processing...";

    const formData = new FormData();
    formData.append("fileA", fileA);
    formData.append("fileB", fileB);

    try {
        const res = await fetch(`${API_BASE}/upload-dual`, {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        storeIdA = data.storeIdA;
        storeIdB = data.storeIdB;
        filenameA = data.filenameA;
        filenameB = data.filenameB;

        document.getElementById("uploadModal").style.display = "none";
        document.getElementById("mainPage").style.display = "block";
    } catch (err) {
        document.getElementById("uploadStatus").innerText = "Upload failed";
    }
};

document.getElementById("askBtn").onclick = async () => {
    const question = document.getElementById("questionInput").value;
    if (!question) return;

    document.getElementById("answer").innerText = "Thinking...";

    const res = await fetch(`${API_BASE}/chat-dual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message: question,
            storeIdA,
            storeIdB,
            filenameA,
            filenameB
        })
    });

    const reader = res.body.getReader();
    let text = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        text += new TextDecoder().decode(value);
        document.getElementById("answer").innerText = text;
    }
};
