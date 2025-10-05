document.addEventListener('DOMContentLoaded', () => {
    let selectedOption = null;

    function selectOption(option) {
        selectedOption = option;
        document.getElementById('btnNASA').classList.toggle('active', option === 'nasa');
        document.getElementById('btnOwnFile').classList.toggle('active', option === 'own');
        document.getElementById('sectionNASA').classList.toggle('active', option === 'nasa');
        document.getElementById('sectionOwnFile').classList.toggle('active', option === 'own');
        document.getElementById('resultsSection').classList.remove('active');
    }

    document.getElementById('fileInput').addEventListener('change', (e) => {
        const file = e.target.files[0];
        document.getElementById('fileName').textContent = file ? `✓ ${file.name}` : '';
    });

    // --- MANEJO DEL FORMULARIO DE NASA KOI ---
    document.getElementById('formNASA').addEventListener('submit', async (e) => {
        e.preventDefault();
        const kepid = document.getElementById('keplerId').value;
        showProcessing();

        try {
            const response = await fetch('/predict_koi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kepid: kepid })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error);

            showSingleResult(data);
        } catch (error) {
            showError(error.message);
        }
    });

    // --- MANEJO DEL FORMULARIO DE ARCHIVO .FITS ---
    document.getElementById('formOwnFile').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('fileInput');

        if (!fileInput.files.length) {
            showError("Por favor, selecciona un archivo .fits.");
            return;
        }

        showProcessing();
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            const response = await fetch('/predict_fits', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error);

            showMultipleResults(data);
        } catch (error) {
            showError(error.message);
        }
    });

    // --- FUNCIONES DE VISUALIZACIÓN ---
    function showProcessing() {
        const resultsSection = document.getElementById('resultsSection');
        resultsSection.classList.add('active');
        document.getElementById('processingDiv').style.display = 'block';
        document.getElementById('resultDiv').style.display = 'none';
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function showError(message) {
        const resultDiv = document.getElementById('resultDiv');
        resultDiv.innerHTML = `
            <div class="result-box result-negative">
                <strong>Error:</strong> ${message}
            </div>
        `;
        document.getElementById('processingDiv').style.display = 'none';
        resultDiv.style.display = 'block';
    }

    function showSingleResult(data) {
        const resultDiv = document.getElementById('resultDiv');
        const probability = data.probability;

        let resultClass = 'result-uncertain';
        let resultMessage = 'Resultado Inconclusivo';

        if (probability >= 60) {
            resultClass = 'result-positive';
            resultMessage = 'Alta Probabilidad de Exoplaneta';
        } else if (probability < 40) {
            resultClass = 'result-negative';
            resultMessage = 'Baja Probabilidad de Exoplaneta';
        }

        resultDiv.innerHTML = `
            <div class="result-box ${resultClass}">
                <div class="probability-display">${probability.toFixed(1)}%</div>
                <div>${resultMessage}</div>
            </div>
            <div class="info-box">
                <h3>Detalles del Análisis</h3>
                <p><strong>Fuente:</strong> ${data.source}</p>
                <p><strong>Kepler ID:</strong> ${data.kepid}</p>
            </div>
        `;
        document.getElementById('processingDiv').style.display = 'none';
        resultDiv.style.display = 'block';
    }

    function showMultipleResults(data) {
        const resultDiv = document.getElementById('resultDiv');
        let resultsHTML = '';

        data.results.forEach(res => {
            const probability = parseFloat(res.probability);
            let resultClass = 'result-uncertain';
            if (probability >= 60) resultClass = 'result-positive';
            else if (probability < 40) resultClass = 'result-negative';

            resultsHTML += `
                <div class="result-box ${resultClass}" style="margin-bottom: 1rem;">
                    <strong>Candidato #${res.candidate_num}</strong>
                    <div class="probability-display" style="font-size: 2rem;">
                        ${res.probability}%
                    </div>
                    <div>Periodo Encontrado: ${res.period} días</div>
                </div>
            `;
        });

        resultDiv.innerHTML = `
            <div class="info-box" style="text-align: left; margin-bottom: 1.5rem;">
                <h3>Análisis de ${data.source}</h3>
                <p>Se encontraron ${data.results.length} señales de tránsito potenciales.</p>
            </div>
            ${resultsHTML}
        `;
        document.getElementById('processingDiv').style.display = 'none';
        resultDiv.style.display = 'block';
    }

    // Iniciar con una opción por defecto
    selectOption('nasa');
    window.selectOption = selectOption;
});
