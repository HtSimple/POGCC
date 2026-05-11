from service import RetrievalService

service = RetrievalService(
    persist_dir=r"D:\python_work\POGCC\demo_index",
    embedding_model=r"D:\python_work\POGCC\bge-small-en-v1.5"
)


def add_files(files):
    return service.batch_ingest(files)


def search_docs(query, top_k=5):
    resp = service.search(query, top_k=top_k)
    return [item.text for item in resp.results]


def list_docs():
    return service.list_documents()


if __name__ == "__main__":
    # 只有新增文件时才执行这句
    files = [
        r"D:\python_work\POGCC\test_text.pdf"
    ]
    print(add_files(files))

    # 后面就一直查，不要重复入库
    results = search_docs("PMLC Model", top_k=3)
    for text in results:
        print("=" * 80)
        print(text[:500])

    results = search_docs("RBS creation", top_k=3)
    for text in results:
        print("=" * 80)
        print(text[:500])
