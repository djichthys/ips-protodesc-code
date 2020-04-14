#!/usr/bin/python3

import os
import pathlib
import requests
import logging
import json
from datetime import datetime
from dataclasses import dataclass, field
from collections import OrderedDict
from typing import List, Iterator, Tuple, Optional, TypeVar, Dict, Union
from ietfdata import datatracker


import xml.etree.ElementTree as domET
from parsers.rfc import rfc_xml_parser,rfc_txt_parser,rfc

T = TypeVar('T')

@dataclass
class RootWorkingDir:
    root  : pathlib.Path = field( default_factory=lambda: pathlib.Path(pathlib.Path.cwd()))
    lock  : pathlib.Path = field(default=None, init=False)
    db    : pathlib.Path = field(default=None, init=False)
    log   : pathlib.Path = field(default=None, init=False)
    rfc   : pathlib.Path = field(default=None, init=False)
    drafts: pathlib.Path = field(default=None, init=False)
    output: pathlib.Path = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

        if not self.root.exists():
            logging.error(f"Root dir <{self.root}> does not exist.")
            if not self.root.is_dir():
                logging.error(f"<{self.root} is not a directory")
            raise AssertionError(f"Error writing to directory {self.root}")

        assert self.root.exists(), f"Root dir <{self.root}> does not exist."
        assert self.root.is_dir(), f"<{self.root} is not a directory"
        # TODO : Also add check to see if directory is writable
        self.lock = self.root / ".lock"
        self.db = self.root / ".db"
        self.log = self.root / ".log"
        self.rfc = self.root / "rfc"
        self.drafts = self.root / "drafts"
        self.output = self.root / "output"


@dataclass(frozen=True)
class FileSysLock:
    fs      : RootWorkingDir
    pid     : int = field(default_factory = os.getpid, init = False)

    def __enter__(self):
        if self.fs.lock.exists():
            with open(self.fs.lock, 'r') as fp:
                _lock = json.load(fp)
                raise AssertionError( f"Process {_lock['pid']} holds lockfile {self.fs.lock}")
            raise AssertionError( f"Another Process holds lockfile {self.fs.lock}") 

        with open(self.fs.lock, 'w') as fp: 
            json.dump( { "start_time": datetime.strftime(datetime.utcnow(), "%Y-%m-%d %H:%M:%S"), 
                    "pid": self.pid }, fp)

        if self.fs.log.exists() : 
            assert self.fs.log.is_file(), f"Prexisting FileSys entry {self.fs.log} not a file"
        else : 
            self.fs.log.write_text("<<<<<<< Start Log >>>>>>>>\n")

        if self.fs.db.exists() : 
            assert self.fs.db.is_file(), f"Prexisting FileSys entry {self.fs.db} not a file"
        else : 
            with open( self.fs.db, "w" ) as fp : 
                json.dump( { "creation time": datetime.strftime(datetime.utcnow(), "%Y-%m-%d %H:%M:%S"), 
                    "drafts": {} , "rfc": {} }, fp)

        self.fs.drafts.mkdir(exist_ok=True) 
        self.fs.rfc.mkdir(exist_ok=True) 
        return self

    def __exit__(self, ex_type, ex, ex_tb):
        assert self.pid == os.getpid(), f"Only pid - {self.pid} allowed to remove {self.fs.lock}"
        self.fs.lock.unlink()
        logging.debug(
            f"pid {self.pid} released {self.fs.lock} at"
            f" {datetime.strftime(datetime.utcnow(),'%Y-%m-%d %H:%M:%S')}")



@dataclass(frozen=True)
class URI:
    uri: str


@dataclass(frozen=True)
class DocURI(URI):
    def __post_init__(self) -> None:
        assert self.uri.startswith("https://www.ietf.org/archive/id")


@dataclass(frozen=True)
class URIxml(DocURI):
    extn: str = field(default='.xml', init=False)

    def __post_init__(self) -> None:
        assert pathlib.Path(
            self.uri
        ).suffix == self.extn, f"uri {self.uri} does not end in .xml"


@dataclass(frozen=True)
class xmlFile(URI):
    extn: str = field(default='.xml', init=False)

    def __post_init__(self) -> None:
        assert pathlib.Path(
            self.uri
        ).suffix == self.extn, f"uri {self.uri} does not end in .xml"


@dataclass(frozen=True)
class txtFile(URI):
    extn: str = field(default='.txt', init=False)

    def __post_init__(self) -> None:
        assert pathlib.Path(
            self.uri
        ).suffix == self.extn, f"uri {self.uri} does not end in .xml"


@dataclass(frozen=True)
class URItext(DocURI):
    extn: str = field(default='.txt', init=False)

    def __post_init__(self) -> None:
        assert pathlib.Path(
            self.uri
        ).suffix == self.extn, f"uri {self.uri} does not end in .txt"


WebURITypes = [URIxml, URItext]
FileURITypes = [xmlFile, txtFile]


@dataclass(frozen=True)
class DownloadOptions:
    force: bool = False  # if set to True, override files in cache


class DownloadURI:
    def __init__(self, name: str, rev: str, extn: str) -> None:
        self.name = name
        self.rev = rev
        self.extn = extn.split(sep=',')
        self.webURITypes = [URIxml, URItext]
        self.fileURITypes = [xmlFile, txtFile]

    def _document_stem(self):
        return f"{self.name}-{self.rev}" if self.rev else f"{self.name}"

    def preferred_doctype(self, webURIBase: str,
                          fileURIBase: str) -> Iterator[Tuple[T, T]]:
        for web_uri, file_uri in zip(self.webURITypes, self.fileURITypes):
            if web_uri.extn in self.extn and web_uri.extn == file_uri.extn:
                yield web_uri( webURIBase + f"/{self._document_stem()}{web_uri.extn}"), \
                        file_uri( fileURIBase + f"/{self.name}/{self.rev}/{self._document_stem()}{file_uri.extn}")

    @property
    def webURI(self) -> T:
        return self._webURI

    @webURI.setter
    def webURI(self, web_uri: T) -> None:
        if type(web_uri) not in self.webURITypes:
            logging.critical( f"type {type(web_uri)} disallowed." \
                    f"Only types {self.webURITypes} allowed." \
                    f"url = {web_uri.uri}")
        assert type(web_uri) in self.webURITypes, f"type {type(web_uri)} disallowed." \
                                                  f"Only types {self.webURITypes} allowed." \
                                                  f"url = {web_uri.uri}"
        self._webURI = web_uri

    @property
    def fileURI(self) -> T:
        return self._fileURI

    @fileURI.setter
    def fileURI(self, file_uri: T) -> None:
        if type(file_uri) not in self.fileURITypes:
            logging.critical( f"type {type(file_uri)} disallowed." \
                    f"Only types {self.fileURITypes} allowed." \
                    f"url = {web_uri.uri}")
        assert type(file_uri) in self.fileURITypes, f"type {type(web_URI)} disallowed." \
                                                    f"Only types {self.webURITypes} allowed." \
                                                    f"url = {web_uri.uri}"
        self._fileURI = file_uri

    def set_used_uri(self, webURI: T, fileURI: T) -> None:
        self.webURI = webURI
        self.fileURI = fileURI


@dataclass
class DownloadClient:
    fslock: FileSysLock
    base_uri: str = "https://www.ietf.org/archive/id"
    dlopts: Optional[DownloadOptions] = field(default_factory=DownloadOptions)

    def __enter__(self) -> None:
        self.session = requests.Session()
        return self

    def __exit__(self, ex_type, ex, ex_tb) -> None:
        self.session.close()
        self.session = None

    def _write_file(self, file_path: pathlib.Path , data: str) -> bool:
        written = False
        file_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

        with open(str(file_path), "w") as fp:
            fp.write(data)
            written = True
        return written

    def download_docs(self, urls: List[DownloadURI]) -> List[Union[xmlFile, txtFile]]:
        docs = list()
        for doc in urls:
            for web_uri, file_uri in doc.preferred_doctype(
                    self.base_uri, str(self.fslock.fs.drafts)):
                filepath = pathlib.Path( file_uri.uri )
                if not self.dlopts.force :
                    if filepath.exists() :
                        break 
                    
                dl = self.session.get(web_uri.uri, verify=True, stream=False)
                if dl.status_code != 200:
                    continue

                logging.debug(f"Downloaded url -- {web_uri.uri}")
                if self._write_file(filepath, dl.text):
                    #doc.set_used_uri(web_uri, file_uri)
                    docs.append(file_uri)
                    logging.debug(f"Written file -- {file_uri.uri}")
                    break
                else:
                    logging.critical(f"Error writing File {file_path.uri}"
                                     f"after downloading url -- {pref_url}")

            else:
                logging.error( f"Could not download any file type for document {doc.name}-{doc.rev}")

        return docs

    def create_db_rec(self, docs: List[DownloadURI], db_content) -> None:
        for d in docs:
            if d.name.startswith("draft"):
                doc_record = db_content['drafts']
                doc_name = f"{d.name}-{d.rev}"
            else:
                doc_record = db_content['rfc']
                doc_name = f"{d.name}"
            kv = doc_record.get(doc_name, None)
            if kv == None:
                doc_record[doc_name] = {"status": "downloaded"}
            else:
                kv["status"] = "downloaded"


def filter_docs(urls: List[DownloadURI],
                doc_filter: Dict[str, Dict[str, str]]) -> List[DownloadURI]:
    filtered_urls = []
    for u in urls:
        cmp_str = f"{u.name}-{u.rev}" if u.name.startswith("draft") else u.name
        if cmp_str in doc_filter:
            continue
        filtered_urls.append(u)
    return filtered_urls


def download_draft_daterange(
    since: str = "1970-01-01T00:00:00",
    until: str = "2038-01-19T03:14:07",
    fs_root: str = str(pathlib.Path.cwd() / "/ietf_docs"), 
    dlopts: DownloadOptions = DownloadOptions()
) -> List[Union[xmlFile, txtFile]]:

    track = datatracker.DataTracker()
    draft_itr = track.documents(since=since,
                                until=until,
                                doctype=track.document_type("draft"))
    urls = []
    for draft in draft_itr:
        for sub_uri in draft.submissions:
            submission = track.submission(sub_uri)
            if submission:
                urls.append(
                    DownloadURI(submission.name, submission.rev,
                                submission.file_types))

    downloaded_docs = []
    # Download files
    with FileSysLock( RootWorkingDir(pathlib.Path(fs_root))) as fslock, \
                    DownloadClient( fslock, dlopts= dlopts) as dlclient:
        logging.basicConfig(filename=fslock.fs.log,
                            filemode='a',
                            format="%(asctime)s | %(levelname)s : %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            level=logging.DEBUG)

        logging.debug(f"Identified urls ---> {len(urls)}")
        for i, u in enumerate(urls):
            logging.debug(f"[{i}] --> {u.name}-{u.rev}")

        downloaded_docs = dlclient.download_docs(urls)
        #dlclient.create_db_rec(downloaded_docs, db_content)

    return downloaded_docs


@dataclass(frozen = True) 
class ProcessDoc: 
    docs : List[Union[xmlFile, txtFile]] 
    fs_root : pathlib.Path = str(pathlib.Path.cwd() / "/ietf_docs")


    def _read_content(self,  doc : Union[xmlFile, txtFile]) -> Tuple[Union[None, rfc.RFC], Union[None,str]] : 
        is_xml  = lambda tdoc :  True if type(doc) is  xmlFile else False
        content, err = None, None
        
        with open( doc.uri, "r") as in_fp :
            if is_xml(doc) : 
                file_content  = in_fp.read() 
                try : 
                    xml = domET.fromstring(file_content) 
                    content = rfc_xml_parser.parse_rfc(xml)
                except domET.ParseError as _pe :
                    # ToDo -- generate an error class to hold error data 
                    logging.error(f"Parse error parsing {doc.uri} : error - {_pe}")
                    err  = str(_pe)
            else : # only other option is text currently
                lines = in_fp.readlines() 
                content = rfc_txt_parser.parse_rfc(lines)
        return (content,err)


    
    def parse_files( self ) -> None : 
        with FileSysLock( RootWorkingDir(pathlib.Path(self.fs_root))) as fs_sys : 
            logging.basicConfig(filename=fs_sys.fs.log,
                            filemode='a',
                            format="%(asctime)s | %(levelname)s : %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            level=logging.DEBUG)

            for doc in self.docs: 
                print(f"Downloaded file -> {doc.uri} , type = {doc.extn}") 
                pt = pathlib.Path( doc.uri )
                if not pt.exists() or not pt.is_file:
                    logging.error(f"file {doc.uri} does not exist. Skipping") 
                    continue

                content, err  = self._read_content( doc )
                if content == None : 
                    print(f"outer error = {err}")
                    continue 
                print(f"content = \n {content}")
        return None 







if __name__ == '__main__':

    default_path = str(pathlib.Path.cwd() / "ciserver/test_dir")
    #docs = download_draft_daterange(since="2020-04-12T00:00:00",\
    #                                until="2020-04-14T00:00:00",\
    #                                fs_root= default_path )
    docs = [ xmlFile( "/home/dejice/work/ietf/ips-protodesc-code/ciserver/test_dir/drafts/draft-ietf-idr-rfc5575bis/20/draft-ietf-idr-rfc5575bis-20.xml" )] 
    docs.append( xmlFile( "/home/dejice/work/ietf/ips-protodesc-code/examples/draft-mcquistin-augmented-ascii-diagrams.xml" )) 
    execute  = ProcessDoc( docs , default_path)
    execute.parse_files()
