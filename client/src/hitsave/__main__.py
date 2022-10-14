import typer

app = typer.Typer()


@app.command()
def serve():
    from hitsave.server import main

    main()


if __name__ == "__main__":
    app()
