# R 4.5.2 with mgcv 1.9.3 was used. The analysis needs only mgcv (shipped with R as a recommended package);
# this installs or updates it from CRAN.
if (!requireNamespace("mgcv", quietly = TRUE)) install.packages("mgcv", repos = "https://cloud.r-project.org")
cat("mgcv", as.character(packageVersion("mgcv")), "\n")
