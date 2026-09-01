input = getArgument();
open(input);
run("8-bit");
run("Thickness", "thickness mask");
print("NOSTOS_DEBUG_NRESULTS=" + nResults);
print("NOSTOS_DEBUG_LABEL=" + getResultLabel(0));
print("NOSTOS_DEBUG_HEADINGS=" + String.getResultsHeadings);
exit();
