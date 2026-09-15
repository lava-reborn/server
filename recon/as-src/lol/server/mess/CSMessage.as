class lol.server.mess.CSMessage
{
   var _body;
   var _name;
   var propList;
   function CSMessage()
   {
      this.propList = new Array();
   }
   function addProp(name, value, duplicateName)
   {
      if(duplicateName == undefined)
      {
         this.propList[name] = value;
      }
      else
      {
         this.propList[duplicateName] = {name:name,value:value};
      }
   }
   function toString()
   {
      var _loc3_;
      if(!this._body)
      {
         this._body = this._name + ";";
         _loc3_ = this.propList.length - 1;
         for(var _loc2_ in this.propList)
         {
            if(this.propList[_loc2_] != undefined)
            {
               if(this.propList[_loc2_].name == undefined)
               {
                  this._body += _loc2_ + "=" + this.propList[_loc2_] + ";";
               }
               else
               {
                  this._body += this.propList[_loc2_].name + "=" + this.propList[_loc2_].value + ";";
               }
            }
         }
      }
      return this._body;
   }
   function get name()
   {
      return this._name;
   }
   function set name(__name)
   {
      this._name = __name;
   }
   function set body(str)
   {
      this._body = str;
   }
   function get body()
   {
      return this._body;
   }
}
