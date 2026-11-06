document.addEventListener('DOMContentLoaded', function() {
    const inputBuscador = document.getElementById('buscadorPlacas');
    const celdas = document.querySelectorAll('.celda');

    if (inputBuscador) {
        inputBuscador.addEventListener('keyup', function() {
            const textoBuscado = this.value.toUpperCase().trim();

            celdas.forEach(celda => {
                const elementoMatricula = celda.querySelector('.matricula-texto');
                const placa = elementoMatricula ? elementoMatricula.textContent.toUpperCase() : "";

                if (textoBuscado === "") {
                    celda.classList.remove('oculta', 'resaltada');
                } else if (placa.includes(textoBuscado)) {
                    celda.classList.remove('oculta');
                    celda.classList.add('resaltada');
                } else {
                    celda.classList.remove('resaltada');
                    celda.classList.add('oculta');
                }
            });
        });
    }
});