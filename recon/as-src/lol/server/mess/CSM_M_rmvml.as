class lol.server.mess.CSM_M_rmvml extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_M_rmvml(idArr)
   {
      super();
      this._name = "rmvml";
      var _loc3_ = 0;
      var _loc4_;
      while(_loc3_ < idArr.length)
      {
         _loc4_ = new lol.data.BigUINT(new lol.data.BigUINTCluster(idArr[_loc3_]));
         this.addProp("id",_loc4_,"id" + _loc3_);
         _loc3_ = _loc3_ + 1;
      }
   }
}
