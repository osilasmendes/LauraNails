const form = document.getElementById("booking-form");
const hoje = form.dataset.hoje;
const [anoAtual, mesAtual] = hoje.split("-").map(Number);
let mes = new Date(anoAtual, mesAtual - 1, 1);
let consulta;

const dias = document.getElementById("dias-calendario");
const titulo = document.getElementById("mes-calendario");
const anterior = document.getElementById("mes-anterior");
const seguinte = document.getElementById("mes-seguinte");
const campoData = document.getElementById("data");
const statusHorarios = document.getElementById("status-horarios");
const horarios = document.getElementById("horarios");
const confirmar = document.getElementById("confirmar-reserva");
const formatoMes = new Intl.DateTimeFormat("pt-BR", {month: "long", year: "numeric"});
const formatoData = new Intl.DateTimeFormat("pt-BR", {dateStyle: "full"});

function mostrarMes() {
    const ano = mes.getFullYear();
    const indice = mes.getMonth();
    titulo.textContent = formatoMes.format(mes);
    anterior.disabled = ano === anoAtual && indice === mesAtual - 1;
    seguinte.disabled = ano >= 9999 && indice === 11;
    dias.replaceChildren();

    for (let vazio = 0; vazio < mes.getDay(); vazio++) {
        dias.append(document.createElement("span"));
    }
    const ultimo = new Date(ano, indice + 1, 0).getDate();
    for (let dia = 1; dia <= ultimo; dia++) {
        const data = new Date(ano, indice, dia);
        const iso = [ano, indice + 1, dia].map(valor => String(valor).padStart(2, "0")).join("-");
        const botao = document.createElement("button");
        botao.type = "button";
        botao.textContent = dia;
        botao.disabled = iso < hoje || data.getDay() < 2;
        botao.setAttribute("aria-label", formatoData.format(data));
        botao.setAttribute("aria-pressed", String(iso === campoData.value));
        botao.addEventListener("click", () => selecionarData(iso, data, botao));
        dias.append(botao);
    }
}

async function selecionarData(iso, data, botao) {
    consulta?.abort();
    consulta = new AbortController();
    const {signal} = consulta;
    campoData.value = iso;
    dias.querySelector('[aria-pressed="true"]')?.setAttribute("aria-pressed", "false");
    botao.setAttribute("aria-pressed", "true");
    horarios.replaceChildren();
    horarios.hidden = true;
    confirmar.disabled = true;
    statusHorarios.textContent = "Consultando horários…";

    try {
        const resposta = await fetch(form.dataset.horarios + "?data=" + iso, {signal});
        if (!resposta.ok) throw new Error("Falha ao consultar a agenda");
        const disponibilidade = await resposta.json();
        if (signal.aborted) return;
        statusHorarios.textContent = disponibilidade.horarios.length
            ? formatoData.format(data)
            : "Sem horários disponíveis para esta data. Escolha outro dia.";

        for (const hora of disponibilidade.horarios) {
            const opcao = document.createElement("label");
            const controle = document.createElement("input");
            controle.type = "radio";
            controle.name = "horario";
            controle.value = hora;
            controle.required = true;
            opcao.append(controle, document.createTextNode(hora));
            horarios.append(opcao);
        }
        horarios.hidden = !disponibilidade.horarios.length;
    } catch (erro) {
        if (signal.aborted) return;
        statusHorarios.textContent = "Não foi possível consultar os horários. Toque na data para tentar de novo.";
    }
}

anterior.addEventListener("click", () => {
    mes = new Date(mes.getFullYear(), mes.getMonth() - 1, 1);
    mostrarMes();
});
seguinte.addEventListener("click", () => {
    mes = new Date(mes.getFullYear(), mes.getMonth() + 1, 1);
    mostrarMes();
});
horarios.addEventListener("change", () => { confirmar.disabled = false; });
mostrarMes();
