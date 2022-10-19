#[actix_rt::main]
async fn main() {
    s3().await;
}

async fn s3() {
    use aws_sdk_s3::{types::ByteStream, Client};
    use std::path::Path;

    dotenv::dotenv().ok();

    let config = aws_config::from_env().region("eu-central-1").load().await;
    let client = Client::new(&config);

    let resp = client.list_buckets().send().await.unwrap();

    for bucket in resp.buckets().unwrap_or_default() {
        println!("bucket: {:?}", bucket.name().unwrap_or_default());
    }

    let body = ByteStream::from_path(Path::new("/home/seabo/xyz/api/Cargo.lock")).await;

    match body {
        Ok(b) => {
            let resp = client
                .put_object()
                .bucket("hitsave-binarystore")
                .key("hi")
                .body(b)
                .send()
                .await
                .unwrap();

            println!("Upload success. Resp: {:?}", resp);
        }
        Err(e) => {
            println!("Error uploading: {:?}", e);
        }
    }
}
