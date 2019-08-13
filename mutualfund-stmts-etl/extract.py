#!/usr/bin/env python
# coding: utf-8

import os
from argparse import ArgumentParser
# import sys, getopt
import csv
import re
import tabula
import logging
import datetime
import csv

from collections import namedtuple
from collections import OrderedDict 
# from data_types import Transaction, TransactionId

# TODO stt to transaction tuple
Transaction = namedtuple('Transaction', ['date', 'txn_type', 'price', 'units', 'nav'])
Scheme = namedtuple('Scheme', ['scheme_name', 'folio_no', 'owner'])

TransactionId = namedtuple('TransactionId', ["folio", "owner", "scheme_norm", "date", "txn_type", "nav"])

logging.basicConfig(level = logging.DEBUG)

CAMS_GAIN_COLUMNS = [70, 110, 160, 215, 242, 273, 330, 370, 425, 475, 510, 547, 590, 635, 679, 720, 762, 815, 830, 870, 915]
KARVY_GAIN_COLUMNS = [67, 106, 148, 185, 234, 273, 340, 394, 431, 469, 520, 582, 640, 696, 755, 800, 845, 890]

CAMS_CAS_COLUMNS = [26, 70, 310, 375, 435, 495, 570]

CAS_LIST_HEADERS = ["scheme_code", "scheme_name", "folio", "owner", "scheme_norm", "date", "txn_type", "price", "units", "nav"]
TXN_LIST_HEADERS = ["scheme_code", "scheme_name", "folio", "owner", "scheme_norm", "date", "txn_type", "price", "units", "nav", "indexed_cost", "stcg", "ltcg_idx", "ltcg_wo_idx", "units_grandf", "nav_grandf", "value_grandf"]

def pdf_to_text(pdf_path, outfile, columns, output_format='tsv', password = None):
    
    logging.debug("Extracting text from pdf - {}".format(pdf_path))
    options_dict = {}
    if password is not None:
        options_dict["password"] = password

    tabula.convert_into(pdf_path, outfile, pages="all", stream=True, guess=False, output_format=output_format, columns=columns, **options_dict)
    # to get text without defined columns
    # tabula.convert_into(pdf_path, "{}-summ.{}".format(output_path, output_format), pages="all", stream=True, guess=False, output_format=output_format, **options_dict)

def read_pdftext_file(outfile):
    with open(outfile, 'r') as content_file:
        content = content_file.read()
    return content    


def write_txns_to_csv(outcsvfile, txns_list):

    with open(outcsvfile, 'w') as csvFile:
        writer = csv.writer(csvFile)
        writer.writerows(txns_list)

    csvFile.close()

def folio_norm_value(folio):
    return folio.split("/",1)[0].strip()

def get_float(num_str):
    return float(num_str.replace(",", ""))

class TxnDict:
    """
    A dictionary object to hold the transactions, with:
    key   : tuple("folio", "owner", "scheme_norm", "date", "txn_type")
    value : list["units", "nav"]

    The scope is used to modify which values are added. 
    'all' : all transactions
    'buy' : only buy transactions
    'sell': only sell transactions
    """  

    def __init__(self, txn_list = [], scope = "all"):
        self.txn_dict = {}

        

        for txn in txn_list:
            logging.debug(txn)
            if scope != "all" and scope != txn[6].lower():
                continue

            d = txn[2:7]
            d.append('%.3f'%(get_float(txn[9])))    
            key = tuple(d)
            value = get_float(txn[8])
            if key in self.txn_dict:
                self.txn_dict[key] += value
                logging.debug("units_nav : {}".format(self.txn_dict[key]))
            else:    
                self.txn_dict[key] = value

        # logging.debug("txn_dict created!!!")
        # logging.debug( self.txn_dict)
            
    def __repr__(self):
        return self.txn_dict
        # s = ""
        # for key in self.txn_dict.keys():
        #     s += ", " + str(key)
        # return s    

    def str_values(self, only_non_zero_values = False):
        lst = []
        for key, units in self.txn_dict.items():
            if only_non_zero_values and abs(units) <= 0.001:
                continue

            lst.append("%s, %s\n" % ( re.sub(r'[()\']+', '', str(key)), units))
        return lst        

    # def non_zero_values_str(self):
        
    #     s = ""
    #     for value in non_zero_values():
    #         s += "\%s\n" % ",".join(value)

    #     return s 

    def __str__(self):
        s = "<class {}> : count = {}\n Non-Zero Unit values are:\n".format(self.__class__.__name__ , len(self.txn_dict.keys()))
        
        for value in self.str_values(only_non_zero_values = True):
            s += value
        # for key, units in self.txn_dict.items():
        #     if units != 0:
        #         s += "\n" + str(key).strip("()") + ", " + str(units) 
        # return "<class {}> : count = {}".format(self.__class__.__name__ , len(self.txn_dict.keys()))
        return s
    
    def __or__(self, other): 
        return self.__add__(other, "or")

    def __ror__(self, other):
        return self.__radd__(other, "or")

    def __add__(self, other, operator=None):
        new_dict = self.txn_dict.copy()
        for key, units in other.txn_dict.items():
            if key in new_dict:
                if operator is None:
                    logging.debug("Inside operator None check")
                    new_dict[key] += units
            else:
                norm_key = self.get_tuple_with_norm_value(key)
                if norm_key in new_dict:
                    if operator is None:
                        new_dict[norm_key] += units
                else:
                    new_dict[key] = units     
        
        c = TxnDict()
        c.txn_dict = new_dict
        return c 

    def __radd__(self, other, operator=None):
        # raise Exception("Called radd on <class TxnDict>. Implement that!! \n Other object type: {}".format(type(other)))

        new_dict = other.txn_dict.copy() if other is not None else {}
        for key, units in self.txn_dict.items():
            if key in new_dict:
                if operator is None:
                    logging.debug("Inside operator None check")
                    new_dict[key] += units
            else:
                norm_key = self.get_tuple_with_norm_value(key)
                if norm_key in new_dict:
                    if operator is None:
                        new_dict[norm_key] += units
                else:
                    new_dict[key] = units     
        
        c = TxnDict()
        c.txn_dict = new_dict
        return c 

    def __sub__(self, other):
        logging.debug("Inside TxnDict.__sub__")
        new_dict = self.txn_dict.copy()
        for key, units in other.txn_dict.items():
            logging.debug("Looking for - {}".format(key))
            if key in new_dict:
                logging.debug("Original Units: {}".format(new_dict[key]))
                new_dict[key] -= units
                logging.debug("Updated Units: {}".format(new_dict[key]))
            else:
                logging.debug("Key did not match - {}".format(key))
                norm_key = self.get_tuple_with_norm_value(key)
                if norm_key in new_dict:
                    new_dict[norm_key] -= units
                else:
                    new_dict[key] = units * -1 

        for key, units in new_dict.items():
            norm_key = self.get_tuple_with_norm_value(key)
            if norm_key != key and norm_key in new_dict:
                new_dict[norm_key] += units
                new_dict[key] = 0
         
        c = TxnDict()
        c.txn_dict = new_dict
        return c             

    def __rsub__(self, other):
        raise Exception("Called rsub on <class TxnDict>. Implement that!! \n Other object type: {}".format(type(other)))

    def get_tuple_with_norm_value(self, tup):
        new_folio = folio_norm_value(tup[0]) if tup[0] is not None else None
        return (new_folio,) + tup[1:]

    @classmethod
    def copy(cls, txn_dict):
        c = cls()
        logging.debug("Creating TxnDict copy !!!! \n\n\n")
        
        c.txn_dict = txn_dict.txn_dict.copy()
        logging.debug(c)
        return c   

def normalize_scheme_name(scheme_name):
    """
    Convert scheme name into a normalized form removing spaces, 'minus' sign.
    Return value: normalized schem_name
    """
    print("scheme_name ; {}".format(scheme_name))

    name = scheme_name.lower()
    try:
        idx = name.index("fund")
    except ValueError:
        i1 = name.index("direct") if "direct" in name else len(name)
        i2 = name.index("growth") if "growth" in name else len(name)
        idx = i1 if i1 < i2 else i2

    sch_name = re.sub(r'[ -_&]+', '', name[:idx].replace(" and", ""))
    sch_name

    sch_suffix = "direct" if "direct" in name[idx:] else ""
    # sch_type = re.sub(r'[ -_]+', '', name[idx+4:].replace("direct", "").replace("plan", ""))
    sch_suffix += "growth" if "growth" in name[idx:] else ""

    scheme_norm = "{}_{}".format(sch_name, sch_suffix)
    return scheme_norm    

def remove_last_item(lst, separator):
    last_index = len(lst) - 1 - lst[::-1].index(separator)
    return lst[0:last_index]

def convert_date(date_str, in_format = "%d-%b-%Y", out_format = "%Y-%m-%d"):
    if len(date_str) == 19 and "T" in date_str:
        in_format = "%Y-%m-%dT%H:%M:%S"
    return datetime.datetime.strptime(date_str, in_format).strftime(out_format)    

# ## Processing CAS

class CasStatement:

    def get_scheme_and_folio(self, cas_list, index):
        
        # a scheme name is too long and spills over to two lines
    #     scheme_name_spillover = False
        if cas_list[index].startswith("Folio"):
            pass
        elif cas_list[index-1].startswith("Folio"):
            index -= 1
        else:
            return "SCHEMA_NOT_DECIPHERED", "00000000"

        scheme_name = remove_last_item(cas_list[index+1], '\t')
        scheme_name = scheme_name.replace("\t","").split("-",1)[1].split("(",1)[0].strip()
        # Remove integers at starting of the name
        scheme_name = re.sub(r'^\d+\s*', '', scheme_name)
        
    #     if scheme_name_spillover:
    #         scheme_name += " " + cas_list[index+2].replace("\t","").split("-",1)[1].split("(",1)[0].strip()
   
        folio = cas_list[index].split("\t")
        folio_no = "".join(folio[0:2]).split(":")[1].strip()  
        
        print("Folio: {}".format(folio_no))
        
        return scheme_name, folio_no

          
    def process_stmt(self, content):

        content = content.replace("Subscription", "Purchase")
        content = content.replace("New Purchase", "Purchase")

        cas_list = content.split("\n")
        cas_list = [l.lstrip("\"\"\t") for l in cas_list]
        print(cas_list)

        cas1 = [l.replace("\t","").replace(" ","") for l in cas_list]
        print(cas1)

        open_index = [i for i, e in enumerate(cas1) if "OpeningUnitBalance" in e]
        close_index = [i for i, e in enumerate(cas1) if "ClosingUnitBalance" in e]
        no_txn_index = [i for i, e in enumerate(cas1) if "Notransactions" in e]
        print(open_index)
        print(close_index)
        print(no_txn_index)

        if len(open_index) != len(close_index):
            raise Exception('length of opening and closing of transaction blocks is not same: ({} != {})'.format(len(open_index), len(close_index)))
        #     log.error('length of opening and closing of transaction blocks is not same: ({} != {})'.format(len(open_index), len(close_index)))

        # At the moment, following transactions are not being catered
        # - Switch Out (Merger) - To Banking & PSU Debt Plan -Drt Growth
        # - Switch In
        # TODO: Add 2-leg transaction for these. See consolidated statement with 'Switch In' entry for this

        purchases = 0
        redemptions = 0
        # TODO: Create a error list, as you go along
        errors = []

        cas_txns_list = []


        for (open_val, close_val) in zip(open_index, close_index):
            if (close_val - open_val) != 2 or (open_val+1) not in no_txn_index:
                
                scheme_name, folio = self.get_scheme_and_folio(cas_list, open_val-2)
                scheme_norm = normalize_scheme_name(scheme_name)
                
                transactions = []
                
                for item in cas_list[open_val+1:close_val]:
                    txn = item.replace("(", "").replace(")", "").split("\t")
                    logging.debug("item - {}".format(item))

                    # txn[1] = txn[1].lower()
                    # print("type => {} - {}".format(type(txn[1]), txn[1]))
                    if (len(txn) != 6) or not txn[1].lower().startswith(("purchase", "redemption")):
                        errors.append("WARNING: Found incompatible transaction - {}".format(txn))
                        continue
        #             print("txn: {}".format(txn))
                    
                    txn[0] = convert_date(txn[0])
                    del txn[5]    
        #             or txn[1].startswith("Subscription")
                    txn[1] = "Buy" if txn[1].lower().startswith("purchase") else "Sell"
                    
                    if txn[1].startswith("Buy"):
                        purchases += 1
                    else:
                        redemptions += 1    
                        
                    transactions.append(Transaction._make(txn))  
        #             print(transactions)

                    # append to list for writing to CSV
                    b = txn[:]   # created copy of list "a" as "b"
                    # skip this step if you are ok with modifying original list
                    b[0:0] = [None, scheme_name, folio, owner, scheme_norm] 
                    cas_txns_list.append(b)
                
                # trade = Folio(None, scheme_name, folio, None, None, transactions)
                # print(trade)
                    
        #         print(cas_list[open+1:close])
                print("\n\n")
                

        print("Total purchases: {}".format(purchases))     
        print("Total redemptions: {}".format(redemptions))

        return cas_txns_list

class CamsGainStatement:

    def process_stmt(self, content):

        cas_list = content.split("\n")
        # create a simple non-tabular view    
        cas1 = [l.lstrip("\"\"\t") for l in cas_list]

        # txn_detail_list = []
        prev_action = ""
        txn_closed = True
        folio = ""
        scheme_name = None
        gain_txn_list = []

        for index, item in enumerate(cas1):
            
            txn = item.split("\t")
            
            if (not txn_closed) and (txn[0] not in ["Purchase", "Redemption", "Total", "Switch In (Merger)"]) :
                continue
            
            if txn[0] in ["Purchase", "Redemption", "Switch In (Merger)"] and prev_action not in ["Purchase", "Redemption", "Switch In (Merger)"] and txn[1] != "Redeemed":
                scheme_name = cas_list[index-1].replace("\t", "").split("(",1)[0].strip()
                scheme_norm = normalize_scheme_name(scheme_name)
                # txn_detail_list.append([scheme_name])
                txn_closed = False
                
            if txn[0] in ["Purchase", "Redemption", "FOLIO No.", "Total", "Switch In (Merger)"]  and txn[1] != "Redeemed":
                print(txn)
                if txn[0] == "FOLIO No." :
                    folio = item.replace("\t", "")
                    folio = folio[9:folio.index("NAME")]
        #             print(folio)
                    # t = [folio]
        #             print(t[1])
                else:    
                    # t = cas_list[index].split("\t")
                    pass
        #         t[0] = index
                # txn_detail_list.append(t)
                prev_action = txn[0]
        #         print(txn)
                
                # TODO: add handling of gains part
                if txn[0] in ["Purchase", "Redemption", "Switch In (Merger)"]  and txn[1] != "Redeemed":
                    a = cas_list[index].split("\t")
                    print(a)
                    if a[0] == "Redemption":
                        gain_txn_list.append([None, scheme_name, folio, None, scheme_norm, convert_date(a[1]), "Sell", a[3], a[2], a[4],None,None,None,None,None,None,None])
        #  Date Units Amount Price
        # namedtuple('Transaction', ['date', 'txn_type', 'price', 'units', 'nav']) 
                                
                    if a[6] in ["Purchase", "Switch In (Merger)"]:
                        txn_type = "Buy" if a[6] == "Purchase" else "Switch In"
                        gain_txn_list.append([None, scheme_name, folio, None, scheme_norm, convert_date(a[7]), txn_type, None, a[8], a[10], a[11], a[15], a[16], a[17], a[12], a[13], a[14]]) 
                
                if txn[0] == "Total" :
                    txn_closed = True
                    scheme_name = None
            
        return gain_txn_list

class KarvyGainStatement:

    def process_stmt(self, content):

        cas_list = content.split("\n")
        # create a simple non-tabular view    
        cas1 = [l.lstrip("\"\"\t") for l in cas_list]

        # txn_detail_list = []
        prev_action = ""
        txn_closed = True
        folio = ""
        scheme_name = None
        gain_txn_list = []

        for index, item in enumerate(cas1):
            
            if item.startswith("Folio No"):
                folio = item.replace("\t", "")
                folio = folio[10:].strip()
                print("folio: {}".format(folio))
                continue
            
            txn = item.split("\t")
            
            if (not txn_closed) and (txn[0] not in ["Purchase", "Redemption", "Total :", "Switch In (Merger)"]) :
                continue
            
            if txn[0] in ["Purchase", "Redemption", "Switch In (Merger)"] and prev_action not in ["Purchase", "Redemption", "Switch In (Merger)"] and txn[1] != "Redeemed":
                scheme_name = cas_list[index-7].replace("\t", "").strip()
                scheme_norm = normalize_scheme_name(scheme_name)
                # txn_detail_list.append([scheme_name])
                txn_closed = False
                
            if txn[0] in ["Purchase", "Redemption", "Total :", "Switch In (Merger)"]  and txn[1] != "Redeemed":
        #         print(txn)
                # t = cas_list[index].split("\t")
                # txn_detail_list.append(t)
                prev_action = txn[0]
                
                print(txn)
                               
                # TODO: add handling of gains part
                if txn[0] in ["Purchase", "Redemption", "Switch In (Merger)"]  and txn[1] != "Redeemed":
                    a = cas_list[index].split("\t")
        #             print(a)
                    if a[0] == "Purchase":
                        gain_txn_list.append([None, scheme_name, folio, None, scheme_norm, convert_date(a[1], "%d-%m-%Y"), "Buy", None, a[3], a[2],None,None,None,None,None,None,None])
        #  Date Units Amount Price
        # namedtuple('Transaction', ['date', 'txn_type', 'price', 'units', 'nav']) 
                                
                    if a[4] == "Redemption":
                        gain_txn_list.append([None, scheme_name, folio, None, scheme_norm, convert_date(a[5], "%d-%m-%Y"), "Sell", a[6], a[10], a[7], a[11], a[12], a[13], a[14], a[15], a[16], a[17]]) 
                
                if txn[0] == "Total :" :
                    txn_closed = True
        #             scheme_name = None

        return gain_txn_list            

class CsvGainStatement:

    def csv_row_to_txn_list(self, row):

        # Input :
        #   Symbol, Entry Trade Date, Buy Average, Qty, Buy Value, Exit Trade Date, Sell Average, Sell Value, Profit
        # Output
        #   ["scheme_code", "scheme_name", "folio", "owner", "scheme_norm", "date", "txn_type", "price", "units", "nav", 
        #     indexed_cost", "stcg", "ltcg_idx", "ltcg_wo_idx", "units_grandf", "nav_grandf", "value_grandf"]   
        
        #    0	 Symbol
        #    1   Folio
        #    2	 Entry Trade Date
        #    3	 Buy Average
        #    4	 Qty
        #    5	 Buy Value
        #    6	 Exit Trade Date
        #    7	 Sell Average
        #    8	 Sell Value
        #    9	 Profit
        #   10	 Period Of Holdings
        #   11	FMV
        #   12	Grandfathered Long Term Profit
        #   13	Taxable Profit     
               
        scheme_name = row[0]
        scheme_norm = normalize_scheme_name(scheme_name)
        
        sell_txn = [None, scheme_name, row[1], None, scheme_norm, convert_date(row[6]), "Sell", row[8], row[4], row[7]]
        buy_txn  = [None, scheme_name, row[1], None, scheme_norm, convert_date(row[2]), "Buy", row[5], row[4], row[3]]
        
        return buy_txn, sell_txn

    def process_stmt(self, csv_path):

        gain_txn_list = []

        with open(csv_path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    logging.debug(f'Column names are {", ".join(row)}')
                    line_count += 1
                else:
                    buy_txn, sell_txn = self.csv_row_to_txn_list(row)
                    gain_txn_list.append(buy_txn)
                    gain_txn_list.append(sell_txn)

        return gain_txn_list

def write_summary(summary_file_path, txn_dict, only_non_zero_values = False):
    with open(summary_file_path, 'w+') as outfile: 
        for i in txn_dict.str_values(only_non_zero_values):
            outfile.write(i)


if __name__ == "__main__":
    
    password = None
    owner = None
    output_format = 'tsv'

    # TODO: Handling CSV input in any order in job-description csv file.
    #   At the moment it has to be the last one in csv.

    # tuple(filename, stmt_type, password, stmt_src) 
    # where :
    #     stmt_type - CAS or GAIN
    #     stmt_src  - (currently) CAMS / KARVY 
    # TODO: Need to add support for FTAMIL / SBFS
    processing_queue = []

    cas_dict = None
    gains_dict = OrderedDict() 

    # logging.debug("Number of arguments: %d argumnets" % (len(sys.argv)))
    # logging.debug("Argument List: %s" % (str(sys.argv))

    # try:
    #     opts, args = getopt.getopt(sys.argv[1:], "hc:",["config="])
    # except getopt.GetoptError:
    #     print('./extract.py -c <configfile>')
    #     sys.exit(2)
    
    # for opt, arg in opts:
    #     if opt == '-h':
    #        print('./extract.py -c <configfile>')
    #        sys.exit()
    #     elif opt in ("-c", "--config"):
    #         job_file_path = arg

    # job_file_path = sys.argv[1] if len(sys.argv) > 1 else 'input/job-desc.csv'

    parser = ArgumentParser()
    parser.add_argument("-c", "--config", dest="job_file_path", default="input/job-desc.csv",
                        help="read pdf files info from csv file", metavar="CONFIG_FILE")

    args = parser.parse_args()                    

    with open(args.job_file_path,'rt') as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)  # skip the headers
        for row in reader:   
            processing_queue.append(tuple(None if v.strip() == "" else v.strip() for v in row)) 
    
    gain_dict = None
    csv_gain_dict = None

    for filename, stmt_type, password, stmt_src in processing_queue:

        stmt_type = stmt_type.upper()
        if stmt_src is not None:
            stmt_src = stmt_src.upper()

        input_path = "input/{}".format(filename)
        output_path = "output/{}".format(os.path.splitext(filename)[0])
        outfile = "{}-{}.{}".format(output_path, stmt_type, output_format)
        summary_file_path = "output/reconciliation_summary.csv"
        summary_file_excl_csv_path = "output/reconciliation_summary_excl_csv_gains.csv"
        detailed_summ_file_path = "output/reconciliation_detailed.csv"

        columns = []
        
        if stmt_type == 'CAS':
            columns = CAMS_CAS_COLUMNS
        elif stmt_type == 'GAIN':
            columns = CAMS_GAIN_COLUMNS if stmt_src == 'CAMS' else KARVY_GAIN_COLUMNS

        if stmt_src != "CSV":
            pdf_to_text(input_path, outfile, columns, output_format, password) 
            content = read_pdftext_file(outfile)

        txn_list = [] 
        headers = []

        if stmt_type == 'CAS':
            txn_list = CasStatement().process_stmt(content)
            if cas_dict is None:
                cas_dict = TxnDict(txn_list, "sell")
            else:
                logging.error("more than one CAS is not accepted. Ignoring ...")
            headers = CAS_LIST_HEADERS
            outcsvfile = "{}-cas.{}".format(output_path, "csv")
        elif stmt_type == 'GAIN':
            if stmt_src == 'CAMS':
                txn_list = CamsGainStatement().process_stmt(content)
            elif stmt_src == 'KARVY':
                txn_list = KarvyGainStatement().process_stmt(content)
            elif stmt_src == 'CSV':
                txn_list = CsvGainStatement().process_stmt(input_path)   
            
            logging.debug("creating TxnDict for : {}".format(filename))
            txn_dict = TxnDict(txn_list, "sell")
            headers = TXN_LIST_HEADERS
            outcsvfile = "{}-gains.{}".format(output_path, "csv")

            if stmt_src == 'CSV':
                csv_gain_dict = csv_gain_dict | txn_dict
            else:
                gain_dict = gain_dict | txn_dict

        txn_list.insert(0, headers)
        write_txns_to_csv(outcsvfile, txn_list)

    logging.debug("cas_dict \n ======>\n{}".format(cas_dict.__repr__()))

    logging.debug("\n\n GainDict AFTER -\n{}".format(gain_dict)) 
    logging.debug("\n\n CASDict -\n{}".format(cas_dict)) 

    recon_dict = cas_dict - gain_dict              
    write_summary(summary_file_excl_csv_path, recon_dict, only_non_zero_values = True)

    recon_dict = recon_dict - csv_gain_dict
    write_summary(summary_file_path, recon_dict, only_non_zero_values = True)
    write_summary(detailed_summ_file_path, recon_dict)

    logging.debug("recon_dict \n ======>\n{}".format(recon_dict))
 
