class lol.core.mail.LetterObject
{
   var _body;
   var _date;
   var _flag;
   var _from;
   var _id;
   var _itemArray;
   var _subj;
   var _time;
   var _to;
   var fullDate;
   var itemDescriptionArr;
   var name;
   var parseDate;
   var type;
   var inbox = true;
   var returnLetter = false;
   var attachObject = false;
   var read = true;
   var outbox = false;
   var full = false;
   var afro = 0;
   var gold = 0;
   function LetterObject(__id, __date, __to, __from, __subj, __flag)
   {
      this.id = __id;
      this.date = __date;
      this.to = __to;
      this.from = __from;
      this.subj = __subj;
      this.flag = __flag;
      this.fullDate = __date;
      this.name = __from;
   }
   function set flag(value)
   {
      this._flag = value;
      this.type = this.flag % 16;
      this.returnLetter = Boolean(this.flag >> 4 & 1);
      this.attachObject = Boolean(this.flag >> 5 & 1);
      this.read = !Boolean(this.flag >> 6 & 1);
      this.outbox = Boolean(this.flag >> 7 & 1);
      this.inbox = !this.outbox;
   }
   function get flag()
   {
      return this._flag;
   }
   function set id(value)
   {
      this._id = value;
   }
   function get id()
   {
      return this._id;
   }
   function set to(value)
   {
      this._to = value;
   }
   function get to()
   {
      return this._to;
   }
   function set from(value)
   {
      this._from = value;
   }
   function get from()
   {
      return this._from;
   }
   function set subj(value)
   {
      this._subj = value;
   }
   function get subj()
   {
      return this._subj;
   }
   function set body(value)
   {
      if(value == undefined)
      {
         return;
      }
      this.itemDescriptionArr = new Array();
      var _loc2_ = value;
      var _loc8_ = _loc2_.indexOf("=?");
      var _loc9_;
      var _loc4_;
      var _loc5_;
      var _loc3_;
      var _loc7_;
      var _loc10_;
      var _loc11_;
      var _loc12_;
      var _loc13_;
      var _loc6_;
      while(_loc8_ != -1)
      {
         _loc2_ = _loc2_.substring(_loc8_,_loc2_.length);
         _loc9_ = _loc2_.indexOf("?=");
         _loc4_ = _loc2_.substring(0,_loc9_);
         _loc5_ = _loc4_.substring(2,4);
         _loc3_ = _loc4_.substring(5,_loc4_.length);
         _loc2_ = _loc2_.substring(_loc9_ + 2,_loc2_.length);
         if(_loc5_ == "HS")
         {
            _loc7_ = "Количество";
            _loc10_ = _loc3_;
         }
         else if(_loc5_ == "HC")
         {
            _loc7_ = "Заряды";
            _loc11_ = _loc3_;
         }
         else if(_loc5_ == "BS")
         {
            _loc7_ = "Износ";
            _loc6_ = _loc3_.indexOf("/");
            _loc12_ = _loc3_.substring(0,_loc6_);
            _loc13_ = _loc3_.substring(_loc6_ + 1,_loc3_.length);
         }
         this.itemDescriptionArr.push({size:_loc10_,hSize:_loc11_,_break:_loc12_,curMaxBreak:_loc13_});
         _loc8_ = _loc2_.indexOf("=?");
      }
      this._body = _loc2_.substring(_loc9_ + 2,_loc2_.length);
   }
   function get body()
   {
      return this._body;
   }
   function set date(value)
   {
      var _loc3_ = value.indexOf(" ");
      this._date = value.substring(0,_loc3_);
      this.time = value.substring(_loc3_ + 1,value.length);
      var _loc6_ = this._date.substr(0,4);
      var _loc5_ = this._date.substr(5,2);
      var _loc4_ = this._date.substr(8,2);
      this.parseDate = _loc4_ + "." + _loc5_ + "." + _loc6_;
   }
   function get date()
   {
      return this._date;
   }
   function set time(value)
   {
      var _loc3_ = new Date();
      var _loc7_ = _loc3_.getHours() - _loc3_.getUTCHours();
      var _loc2_ = Number(value.substr(0,2));
      var _loc5_ = value.substr(3,2);
      var _loc6_ = value.substr(6,2);
      _loc2_ = (_loc2_ + _loc7_) % 24;
      this._time = _loc2_ + ":" + _loc5_ + ":" + _loc6_;
   }
   function get time()
   {
      return this._time;
   }
   function set itemArray(arr)
   {
      this._itemArray = new Array();
      var _loc2_;
      var _loc3_;
      if(this.attachObject)
      {
         _loc2_ = 0;
         while(_loc2_ < arr.length)
         {
            _loc3_ = this.createItem(arr[_loc2_]);
            this._itemArray.push(_loc3_);
            _loc3_.setProp("size",this.itemDescriptionArr[_loc2_].size);
            _loc3_.setProp("__break",this.itemDescriptionArr[_loc2_]._break);
            _loc3_.setProp("max_break_cur",this.itemDescriptionArr[_loc2_].curMaxBreak);
            _loc3_.setProp("use_count",this.itemDescriptionArr[_loc2_].hSize);
            _loc2_ = _loc2_ + 1;
         }
      }
   }
   function get itemArray()
   {
      return this._itemArray;
   }
   function createItem(oid)
   {
      var _loc2_;
      if(oid != "0" && oid.length > 1)
      {
         _loc2_ = lol.core.objects.ItemFactory.create(oid,true);
         return _loc2_;
      }
   }
}
