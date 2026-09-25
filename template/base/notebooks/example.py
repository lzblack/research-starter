import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from paper_outputs import Outputs

    return Outputs, np, pd, plt


@app.cell
def _(Outputs, pd):
    outputs = Outputs("example")
    data = pd.read_parquet(outputs.input("data/derived/example.parquet"))
    return data, outputs


@app.cell
def _(data, outputs):
    outputs.variable("example_n_obs", f"{len(data):,}")
    return


@app.cell
def _(data, np, outputs, pd):
    def slope(columns):
        design = np.column_stack([np.ones(len(data))] + [data[c].to_numpy() for c in columns])
        coefficients, *_ = np.linalg.lstsq(design, data["y"].to_numpy(), rcond=None)
        return coefficients[1]

    estimates = pd.DataFrame(
        {
            "Model": ["Bivariate", "With control z"],
            "Estimate for x": [f"{slope(['x']):.2f}", f"{slope(['x', 'z']):.2f}"],
        }
    )
    outputs.table("example_table", estimates, "Synthetic example estimates")
    return


@app.cell
def _(data, outputs, plt):
    figure, axes = plt.subplots(figsize=(4, 3))
    axes.scatter(data["x"], data["y"], s=4, alpha=0.5)
    axes.set_xlabel("x")
    axes.set_ylabel("y")
    figure.tight_layout()
    outputs.figure("example_figure", figure)
    return


if __name__ == "__main__":
    app.run()
