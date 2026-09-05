// QCAD Community (GPLv3) batch rewrite: DXF -> DXF R15.
// Invoked: qcad -no-gui -allow-multiple-instances -autostart <this> -- <in.dxf> <out.dxf>

function qcadArgv() {
    if (typeof args !== "undefined") {
        return args;
    }
    return [];
}

function filesFromArgs(argv) {
    var infile = "";
    var outfile = "";
    for (var i = 0; i < argv.length; i++) {
        if (argv[i] === "--" && i + 2 < argv.length) {
            infile = argv[i + 1];
            outfile = argv[i + 2];
            break;
        }
    }
    if (!infile && argv.length >= 2) {
        infile = argv[argv.length - 2];
        outfile = argv[argv.length - 1];
    }
    return [infile, outfile];
}

var pair = filesFromArgs(qcadArgv());
var infile = pair[0];
var outfile = pair[1];
if (!infile || !outfile) {
    print("usage: qcad -no-gui -autostart qcad_normalize.js -- in.dxf out.dxf");
    quit();
}

var di = new RDocumentInterface();
if (di.importFile(infile) !== RDocumentInterface.IoErrorNoError) {
    print("qcad import failed: " + infile);
    quit();
}

var exported = false;
if (typeof di.exportFile === "function") {
    exported = di.exportFile(outfile, "DXF R15") || di.exportFile(outfile);
}
if (!exported) {
    print("qcad export failed: " + outfile);
    quit();
}
print("qcad ok");
quit();
