from dataclasses import dataclass


@dataclass
class Director:

    name: str
    ic: str
    dob: str
    nationality: str
    residential_address: str


@dataclass
class Shareholder:

    type: str
    name: str
    id_type: str
    id_no: str
    nationality: str
    race: str
    gender: str
    dob: str
    address: str
    shares: str
    share_type: str


@dataclass
class BeneficialOwner:

    name: str
    ic: str
    nationality: str
    designation: str
    bo_status: str
    direct_ownership: str
    voting_shares: str
    date_of_becoming: str
    date_of_cessation: str


@dataclass
class Directorship:

    company_name: str
    reg_no: str