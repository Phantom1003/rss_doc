var now = undefined;

function show_current() {
    var div = document.createElement("div");
    div.setAttribute("class", "current_timestamp fixed-bottom");
    div.innerHTML = "Last Update " + new Date().toLocaleString();  
    var header = document.body.querySelectorAll('header')[0];
    document.body.insertBefore(div, header);
}

async function get_timestamp() {
    await fetch("/timestamp")
        .then((res) => res.text())
        .then((text) => {
            console.log(text);
            if (now == undefined) {
                now = text;
            } else if (now != text) {
                window.location.reload();
            }
        })
        .catch((e) => console.error(e));
}

show_current();

setInterval(function () {
    get_timestamp();
}, 1000);

