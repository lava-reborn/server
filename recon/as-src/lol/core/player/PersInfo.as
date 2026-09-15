class lol.core.player.PersInfo
{
   var __avatar;
   var _ally;
   var _persType;
   var _resID;
   var _sex;
   var setResID;
   function PersInfo()
   {
   }
   function get resID()
   {
      return this._resID;
   }
   function set resID(value)
   {
      this._resID = value;
   }
   function setAvatar(id, sex, buy)
   {
      this.avatar = {id:id,sex:sex,buy:buy};
   }
   function set avatar(obj)
   {
      this.__avatar = obj;
   }
   function get avatar()
   {
      return this.__avatar;
   }
   function set ally(value)
   {
      this._ally = value != undefined ? value : value;
   }
   function get ally()
   {
      return this._ally;
   }
   function set sex(s)
   {
      this._sex = s;
      this.persType = s;
   }
   function get sex()
   {
      return this._sex;
   }
   function get boolSex()
   {
      return this._sex < 128;
   }
   function set persType(pt)
   {
      this._persType = pt;
   }
   function get persType()
   {
      var _loc2_ = !this.setResID ? this._persType : this.setResID;
      return _loc2_;
   }
   function set sexString(s)
   {
      if(s == "male")
      {
         this.sex = 0;
      }
      else if(s == "female")
      {
         this.sex = 128;
      }
      else
      {
         this.sex = undefined;
      }
   }
   function get sexString()
   {
      if(this._sex < 128)
      {
         return "male";
      }
      return "female";
   }
}
